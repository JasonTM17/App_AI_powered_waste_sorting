"""Service-only bridge from the local hardware runtime to Supabase Postgres.

This script syncs safe operational state upward. It does not expose camera
frames, UART commands, or training controls to browser users.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.agent.api import _training_status
from app.agent.operations_store import OperationsStore
from app.core.history import HistoryService
from app.utils.paths import db_path, operations_db_path, project_root

SUPABASE_DB_ENV = "TRASH_SORTER_SUPABASE_DATABASE_URL"
DEMO_TARGET_ENV = "TRASH_SORTER_DEMO_HARDWARE_TARGET"
LOGGER = logging.getLogger("supabase-hardware-bridge")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Sync local hardware state to Supabase.")
    parser.add_argument("--once", action="store_true", help="Run one sync cycle and exit.")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between sync cycles.")
    parser.add_argument("--history-limit", type=int, default=200, help="Recent history rows to sync.")
    parser.add_argument("--operations-db", type=Path, default=operations_db_path())
    parser.add_argument("--history-db", type=Path, default=db_path())
    args = parser.parse_args()

    database_url = os.getenv(SUPABASE_DB_ENV, "").strip()
    if not database_url:
        raise SystemExit(f"Set {SUPABASE_DB_ENV} to the Supabase pooled/direct Postgres URL.")

    retry_delay = max(1.0, args.interval)
    while True:
        try:
            with psycopg.connect(database_url, autocommit=False, prepare_threshold=None) as conn:
                sync_once(conn, args.operations_db, args.history_db, args.history_limit)
                conn.commit()
            retry_delay = max(1.0, args.interval)
            if args.once:
                return 0
            time.sleep(retry_delay)
        except psycopg.Error as exc:
            if args.once:
                raise
            LOGGER.warning("Supabase sync failed; retrying in %.1fs: %s", retry_delay, exc)
            time.sleep(retry_delay)
            retry_delay = min(30.0, retry_delay * 2)


def sync_once(conn: psycopg.Connection[Any], operations_db: Path, history_db: Path, history_limit: int) -> None:
    bin_readings = sync_operations(conn, operations_db)
    sync_demo_hardware_targets(conn, bin_readings)
    sync_history(conn, history_db, history_limit)
    sync_training_status(conn)


def sync_operations(conn: psycopg.Connection[Any], operations_db: Path) -> dict[int, dict[str, Any]]:
    # This side of the bridge must always read the hardware machine's local
    # SQLite state. Destination credentials may also be present in the process
    # environment and must not redirect the source store back to Supabase.
    store = OperationsStore(operations_db, database_url="")
    bin_readings: dict[int, dict[str, Any]] = {}
    try:
        for device in store.list_devices():
            device_active = _db_bool(conn, "devices", "active", bool(device["active"]))
            device_status = str(device["status"] or "").strip()
            bridge_status = device_status if device_status in {"warning", "maintenance"} else "online"
            bridge_message = str(device["message"] or "").strip() or "Hardware bridge synced to Supabase."
            conn.execute(
                """
                insert into public.devices
                  (device_id, device_name, location, owner_username, status, message, active, created_at, last_seen_at, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s, now(), now(), now())
                on conflict (device_id) do update set
                  device_name = excluded.device_name,
                  location = excluded.location,
                  owner_username = excluded.owner_username,
                  status = excluded.status,
                  message = excluded.message,
                  active = excluded.active,
                  last_seen_at = excluded.last_seen_at,
                  updated_at = now()
                """,
                (
                    device["device_id"],
                    device["device_name"],
                    device["location"],
                    device["owner_username"],
                    bridge_status,
                    bridge_message,
                    device_active,
                ),
            )

        for station in store.list_bin_map(include_inactive=True)["stations"]:
            station_verified = _db_bool(conn, "bin_stations", "coordinate_verified", bool(station["coordinate_verified"]))
            station_active = _db_bool(conn, "bin_stations", "active", bool(station["active"]))
            conn.execute(
                """
                insert into public.bin_stations
                  (station_id, name, area, address, latitude, longitude, status, coordinate_verified,
                   source, assigned_owner_username, device_id, note, seed_source, active, created_at, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
                on conflict (station_id) do update set
                  name = excluded.name,
                  area = excluded.area,
                  address = excluded.address,
                  latitude = excluded.latitude,
                  longitude = excluded.longitude,
                  status = excluded.status,
                  coordinate_verified = excluded.coordinate_verified,
                  source = excluded.source,
                  assigned_owner_username = excluded.assigned_owner_username,
                  device_id = excluded.device_id,
                  note = excluded.note,
                  seed_source = excluded.seed_source,
                  active = excluded.active,
                  updated_at = now()
                """,
                (
                    station["station_id"],
                    station["name"],
                    station["area"],
                    station["address"],
                    station.get("latitude"),
                    station.get("longitude"),
                    station["status"],
                    station_verified,
                    station["seed_source"],
                    station["owner_username"],
                    station["device_id"],
                    station["note"],
                    station["seed_source"],
                    station_active,
                ),
            )
            for child in station["bins"]:
                bin_readings[int(child["bin_index"])] = {
                    "fill_percent": float(child["fill_percent"] or 0),
                    "status": str(child["status"] or fullness_status(float(child["fill_percent"] or 0))),
                    "updated_at": child.get("updated_at"),
                }
                child_active = _db_bool(conn, "bins", "active", bool(child["active"]))
                conn.execute(
                    """
                    insert into public.bins
                      (bin_id, station_id, command, bin_index, label, fill_percent, status, active, created_at, updated_at)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, now(), now())
                    on conflict (bin_id) do update set
                      fill_percent = excluded.fill_percent,
                      status = excluded.status,
                      active = excluded.active,
                      updated_at = now()
                    """,
                    (
                        child["bin_id"],
                        child["station_id"],
                        child["command"],
                        child["bin_index"],
                        child["label"],
                        child["fill_percent"],
                        child["status"],
                        child_active,
                    ),
                )

        for alert in store.list_alerts(include_resolved=True):
            conn.execute(
                """
                insert into public.alerts
                  (alert_id, station_id, bin_id, device_id, severity, title, message, status, source,
                   actor_username, derived, created_at, updated_at, resolved_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, nullif(%s, '')::timestamptz)
                on conflict (alert_id) do update set
                  severity = excluded.severity,
                  message = excluded.message,
                  status = excluded.status,
                  updated_at = excluded.updated_at,
                  resolved_at = excluded.resolved_at
                """,
                (
                    alert["alert_id"],
                    alert["station_id"],
                    alert["bin_id"],
                    alert["device_id"],
                    alert["severity"],
                    alert["title"],
                    alert["message"],
                    alert["status"],
                    alert["source"],
                    alert["actor_username"],
                    bool(alert["derived"]),
                    alert["created_at"],
                    alert["updated_at"],
                    alert["resolved_at"],
                ),
            )
    finally:
        store.close()
    return bin_readings


def sync_demo_hardware_targets(conn: psycopg.Connection[Any], bin_readings: dict[int, dict[str, Any]]) -> None:
    if os.getenv(DEMO_TARGET_ENV, "").strip() != "1" or not bin_readings:
        return
    _ensure_demo_target_table(conn)
    targets = conn.execute(
        """
        select owner_username, station_id, bin_id, bin_index
        from public.demo_hardware_targets
        where active = true
        order by selected_at desc
        limit 1
        """
    ).fetchall()
    applied = 0
    for owner_username, station_id, bin_id, bin_index in targets:
        reading = bin_readings.get(int(bin_index))
        if not reading:
            continue
        percent = max(0.0, min(100.0, float(reading["fill_percent"])))
        status = fullness_status(percent)
        conn.execute(
            """
            update public.bins
               set fill_percent = %s,
                   status = %s,
                   updated_at = now()
             where station_id = %s
               and bin_index = %s
               and (%s::text = '' or bin_id = %s)
            """,
            (percent, status, station_id, int(bin_index), str(bin_id or ""), str(bin_id or "")),
        )
        conn.execute(
            """
            update public.demo_hardware_targets
               set last_applied_at = now(),
                   last_percent = %s
             where owner_username = %s
            """,
            (percent, owner_username),
        )
        if percent >= 95:
            conn.execute(
                """
                insert into public.alerts
                  (alert_id, station_id, bin_id, device_id, severity, title, message, status, source,
                   actor_username, derived, created_at, updated_at)
                values (%s, %s, %s, '', 'danger', 'Thùng rác đã đầy', %s, 'open', 'demo_hardware_target',
                        %s, true, now(), now())
                on conflict (alert_id) do update set
                  severity = excluded.severity,
                  message = excluded.message,
                  status = 'open',
                  updated_at = now()
                """,
                (
                    f"demo-fullness-{station_id}-{int(bin_index)}",
                    station_id,
                    str(bin_id or ""),
                    f"Cảm biến demo báo thùng {int(bin_index)} đã đầy {round(percent)}%.",
                    str(owner_username or ""),
                ),
            )
        applied += 1
    if applied:
        LOGGER.info("Applied %d demo hardware target fullness update(s).", applied)


def sync_history(conn: psycopg.Connection[Any], history_db: Path, limit: int) -> None:
    if not _table_exists(conn, "history"):
        return
    if not history_db.exists():
        return
    service = HistoryService(history_db)
    skipped_without_owner = 0
    try:
        rows = service.query(limit=max(1, limit))
    finally:
        service.close()
    for row in rows:
        owner_username = str(getattr(row, "owner_username", "") or "").strip()
        if not owner_username:
            skipped_without_owner += 1
            continue
        row_id = int(row.id)
        conn.execute(
            """
            insert into public.history
              (local_history_id, device_id, owner_username, ts, cls_id, cls_name, confidence,
               route_label, bin_index, uart_command, ack_status, rtt_ms, image_available,
               display_label, label_status, label_source, label_confidence,
               reviewed_by, reviewed_at, review_note)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s)
            on conflict (device_id, local_history_id) do update set
              owner_username = excluded.owner_username,
              ack_status = excluded.ack_status,
              rtt_ms = excluded.rtt_ms,
              display_label = excluded.display_label,
              label_status = excluded.label_status,
              label_source = excluded.label_source,
              label_confidence = excluded.label_confidence,
              reviewed_by = excluded.reviewed_by,
              reviewed_at = excluded.reviewed_at,
              review_note = excluded.review_note
            """,
            (
                row_id,
                str(getattr(row, "device_id", "") or "local-trash-sorter"),
                owner_username,
                _parse_ts(str(row.ts)),
                int(row.cls_id),
                str(row.cls_name),
                float(row.conf),
                getattr(row, "route_label", None),
                getattr(row, "bin_index", None),
                getattr(row, "uart_command", None),
                getattr(row, "ack_status", None),
                getattr(row, "rtt_ms", None),
                bool(getattr(row, "image_path", None) or getattr(row, "annotated_path", None)),
                getattr(row, "display_label", None),
                getattr(row, "label_status", None),
                getattr(row, "label_source", None),
                getattr(row, "label_confidence", None),
                getattr(row, "reviewed_by", None),
                getattr(row, "reviewed_at", None),
                getattr(row, "review_note", None),
            ),
        )
    if skipped_without_owner:
        LOGGER.warning("Skipped %d history row(s) without an owner username.", skipped_without_owner)


def sync_training_status(conn: psycopg.Connection[Any]) -> None:
    if not _table_exists(conn, "training_jobs"):
        return
    status = _training_status(project_root())
    payload = status.model_dump(mode="json")
    metrics = {
        "precision": payload.get("precision"),
        "recall": payload.get("recall"),
        "map50": payload.get("map50"),
        "map5095": payload.get("map5095"),
    }
    conn.execute(
        """
        insert into public.training_jobs
          (job_id, run_name, status, progress_percent, metrics, message, best_model_ref, last_model_ref, updated_at)
        values ('local-current', %s, %s, %s, %s, %s, %s, %s, now())
        on conflict (job_id) do update set
          run_name = excluded.run_name,
          status = excluded.status,
          progress_percent = excluded.progress_percent,
          metrics = excluded.metrics,
          message = excluded.message,
          best_model_ref = excluded.best_model_ref,
          last_model_ref = excluded.last_model_ref,
          updated_at = now()
        """,
        (
            payload.get("run_name") or "",
            "running" if payload.get("running") else "idle",
            float(payload.get("progress_percent") or 0),
            Jsonb(metrics),
            payload.get("message") or "",
            payload.get("best_model_path") or "",
            payload.get("last_model_path") or "",
        ),
    )


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


_COLUMN_TYPE_CACHE: dict[tuple[str, str], str] = {}
_TABLE_EXISTS_CACHE: dict[str, bool] = {}


def fullness_status(percent: float) -> str:
    if percent >= 95:
        return "full"
    if percent >= 80:
        return "warning"
    return "normal"


def _ensure_demo_target_table(conn: psycopg.Connection[Any]) -> None:
    if _TABLE_EXISTS_CACHE.get("demo_hardware_targets"):
        return
    conn.execute(
        """
        create table if not exists public.demo_hardware_targets (
          owner_username text primary key,
          station_id text not null references public.bin_stations(station_id) on delete cascade,
          bin_id text not null default '',
          bin_index integer not null check (bin_index between 1 and 3),
          selected_by text not null default '',
          selected_at timestamptz not null default now(),
          last_applied_at timestamptz,
          last_percent numeric(5,2),
          active boolean not null default true
        )
        """
    )
    conn.execute(
        "create index if not exists idx_demo_hardware_targets_selected_at "
        "on public.demo_hardware_targets(selected_at desc) where active"
    )
    _TABLE_EXISTS_CACHE["demo_hardware_targets"] = True


def _db_bool(conn: psycopg.Connection[Any], table: str, column: str, value: bool) -> bool | int:
    key = (table, column)
    data_type = _COLUMN_TYPE_CACHE.get(key)
    if data_type is None:
        row = conn.execute(
            """
            select data_type
            from information_schema.columns
            where table_schema = 'public'
              and table_name = %s
              and column_name = %s
            """,
            (table, column),
        ).fetchone()
        data_type = str(row[0]) if row else "boolean"
        _COLUMN_TYPE_CACHE[key] = data_type
    if data_type in {"integer", "bigint", "smallint", "numeric"}:
        return 1 if value else 0
    return value


def _table_exists(conn: psycopg.Connection[Any], table: str) -> bool:
    cached = _TABLE_EXISTS_CACHE.get(table)
    if cached is not None:
        return cached
    row = conn.execute(
        """
        select exists (
          select 1
          from information_schema.tables
          where table_schema = 'public'
            and table_name = %s
        )
        """,
        (table,),
    ).fetchone()
    exists = bool(row[0]) if row else False
    _TABLE_EXISTS_CACHE[table] = exists
    return exists


if __name__ == "__main__":
    raise SystemExit(main())
