"""Service-only bridge from the local hardware runtime to Supabase Postgres.

This script syncs safe operational state upward. It does not expose camera
frames, UART commands, or training controls to browser users.
"""

from __future__ import annotations

import argparse
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync local hardware state to Supabase.")
    parser.add_argument("--once", action="store_true", help="Run one sync cycle and exit.")
    parser.add_argument("--interval", type=float, default=10.0, help="Seconds between sync cycles.")
    parser.add_argument("--history-limit", type=int, default=200, help="Recent history rows to sync.")
    parser.add_argument("--operations-db", type=Path, default=operations_db_path())
    parser.add_argument("--history-db", type=Path, default=db_path())
    args = parser.parse_args()

    database_url = os.getenv(SUPABASE_DB_ENV, "").strip()
    if not database_url:
        raise SystemExit(f"Set {SUPABASE_DB_ENV} to the Supabase pooled/direct Postgres URL.")

    while True:
        with psycopg.connect(database_url, autocommit=False) as conn:
            sync_once(conn, args.operations_db, args.history_db, args.history_limit)
            conn.commit()
        if args.once:
            return 0
        time.sleep(max(2.0, args.interval))


def sync_once(conn: psycopg.Connection[Any], operations_db: Path, history_db: Path, history_limit: int) -> None:
    sync_operations(conn, operations_db)
    sync_history(conn, history_db, history_limit)
    sync_training_status(conn)


def sync_operations(conn: psycopg.Connection[Any], operations_db: Path) -> None:
    store = OperationsStore(operations_db)
    try:
        for device in store.list_devices():
            conn.execute(
                """
                insert into public.devices
                  (device_id, device_name, location, owner_username, status, message, active, last_seen_at, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s, now(), now())
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
                    device["status"],
                    device["message"],
                    bool(device["active"]),
                ),
            )

        for station in store.list_bin_map(include_inactive=True)["stations"]:
            conn.execute(
                """
                insert into public.bin_stations
                  (station_id, name, area, address, latitude, longitude, status, coordinate_verified,
                   assigned_owner_username, device_id, note, seed_source, active, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                on conflict (station_id) do update set
                  name = excluded.name,
                  area = excluded.area,
                  address = excluded.address,
                  latitude = excluded.latitude,
                  longitude = excluded.longitude,
                  status = excluded.status,
                  coordinate_verified = excluded.coordinate_verified,
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
                    bool(station["coordinate_verified"]),
                    station["owner_username"],
                    station["device_id"],
                    station["note"],
                    station["seed_source"],
                    bool(station["active"]),
                ),
            )
            for child in station["bins"]:
                conn.execute(
                    """
                    insert into public.bins
                      (bin_id, station_id, command, bin_index, label, fill_percent, status, active, updated_at)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, now())
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
                        bool(child["active"]),
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


def sync_history(conn: psycopg.Connection[Any], history_db: Path, limit: int) -> None:
    if not history_db.exists():
        return
    service = HistoryService(history_db)
    for row in service.query(limit=max(1, limit)):
        row_id = int(row.id)
        conn.execute(
            """
            insert into public.history
              (local_history_id, device_id, owner_username, ts, cls_id, cls_name, confidence,
               route_label, bin_index, uart_command, ack_status, rtt_ms, image_available)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (device_id, local_history_id) do update set
              owner_username = excluded.owner_username,
              ack_status = excluded.ack_status,
              rtt_ms = excluded.rtt_ms
            """,
            (
                row_id,
                str(getattr(row, "device_id", "") or "local-trash-sorter"),
                str(getattr(row, "owner_username", "") or ""),
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
            ),
        )


def sync_training_status(conn: psycopg.Connection[Any]) -> None:
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


if __name__ == "__main__":
    raise SystemExit(main())
