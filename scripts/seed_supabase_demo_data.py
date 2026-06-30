"""Seed persistent teacher-demo data for every active User account."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg

DEMO_SOURCE = "demo_teacher_2026"
DATABASE_ENV_NAMES = (
    "TRASH_SORTER_SUPABASE_DATABASE_URL",
    "POSTGRES_URL",
    "DATABASE_URL",
    "TRASH_SORTER_AUTH_DATABASE_URL",
)
CLASSES = (
    (3, "Plastic bottle", "Tái chế", 3, "I"),
    (8, "Paper", "Tái chế", 3, "I"),
    (14, "Organic", "Hữu cơ", 1, "O"),
    (21, "Ceramic", "Vô cơ", 2, "R"),
    (31, "Aluminum can", "Tái chế", 3, "I"),
    (5, "Cardboard", "Tái chế", 3, "I"),
    (10, "Glass bottle", "Tái chế", 3, "I"),
    (17, "Paper bag", "Tái chế", 3, "I"),
    (23, "Disposable tableware", "Vô cơ", 2, "R"),
    (28, "Textile", "Vô cơ", 2, "R"),
    (36, "Wood", "Hữu cơ", 1, "O"),
    (39, "Liquid", "Hữu cơ", 1, "O"),
)
BIN_LABELS = ((1, "O", "Hữu cơ"), (2, "R", "Vô cơ"), (3, "I", "Tái chế"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write demo data. Default is dry-run.")
    parser.add_argument("--history-count", type=int, default=240)
    parser.add_argument(
        "--username",
        action="append",
        default=[],
        help="Seed only this active User username. Repeat for multiple users.",
    )
    args = parser.parse_args()
    database_url = next((os.getenv(name, "").strip() for name in DATABASE_ENV_NAMES if os.getenv(name, "").strip()), "")
    if not database_url:
        raise SystemExit(f"Set one of: {', '.join(DATABASE_ENV_NAMES)}")

    with psycopg.connect(database_url, autocommit=False, prepare_threshold=None) as conn:
        users = active_usernames(conn)
        if args.username:
            requested = {item.strip() for item in args.username if item.strip()}
            users = [username for username in users if username in requested]
            missing = sorted(requested - set(users))
            if missing:
                raise SystemExit(f"Active user account(s) not found: {', '.join(missing)}")
        print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
        print(f"Users: {len(users)}")
        history_count = max(180, args.history_count)
        print(f"Planned: {len(users) * 3} stations, {len(users) * 9} bins, "
              f"{len(users) * history_count} history rows, "
              f"{len(users) * 3} schedules, {len(users) * 2} alerts")
        if not args.apply:
            conn.rollback()
            return 0
        require_demo_schema(conn)
        for username in users:
            seed_user(conn, username, history_count)
        conn.commit()
        verify_seed(conn, users, history_count)
        print(f"Applied persistent demo data with seed_source={DEMO_SOURCE}.")
    return 0


def active_usernames(conn: psycopg.Connection[Any]) -> list[str]:
    users: set[str] = set()
    if table_exists(conn, "profiles"):
        rows = conn.execute(
            """select username from public.profiles
                 where role = 'user'
                   and coalesce(active::text, 'true') not in ('0', 'false', 'f', 'no')
                   and username <> ''"""
        ).fetchall()
        users.update(str(row[0]).strip() for row in rows if str(row[0]).strip())
    if table_exists(conn, "accounts"):
        rows = conn.execute(
            """
            select username from public.accounts
             where role = 'user'
               and coalesce(is_active::text, 'true') not in ('0', 'false', 'f', 'no')
               and coalesce(username, '') <> ''
            """
        ).fetchall()
        users.update(str(row[0]).strip() for row in rows if str(row[0]).strip())
    return sorted(users)


def seed_user(conn: psycopg.Connection[Any], username: str, history_count: int) -> None:
    digest = hashlib.md5(username.encode("utf-8")).hexdigest()
    device_id = f"demo-device-{digest[:12]}"
    device_active = db_bool(conn, "devices", "active", True)
    station_ids = ensure_three_stations(conn, username, digest, device_id)
    conn.execute(
        """
        insert into public.devices
          (device_id, device_name, location, owner_username, status, message, active,
           last_seen_at, created_at, updated_at)
        values (%s, %s, %s, %s, 'online', %s, %s, now(), now(), now())
        on conflict (device_id) do update set
          owner_username = excluded.owner_username, status = 'online', message = excluded.message,
          active = excluded.active, last_seen_at = now(), updated_at = now()
        """,
        (
            device_id, f"EcoSort Demo - {username}", "Khu trình diễn", username,
            f"Seed: {DEMO_SOURCE}", device_active,
        ),
    )
    for station_number, station_id in enumerate(station_ids, start=1):
        seed_bins(conn, station_id, station_number)
    seed_history(conn, username, device_id, digest, history_count)
    seed_schedule_and_alert(conn, username, station_ids)


def ensure_three_stations(
    conn: psycopg.Connection[Any], username: str, digest: str, device_id: str
) -> list[str]:
    station_ids = [f"user-{digest[:12]}-{index}" for index in range(1, 4)]
    coordinates = ((10.8020001, 106.7406138), (10.8276722, 106.7215390), (10.8502385, 106.7541974))
    station_active = db_bool(conn, "bin_stations", "active", True)
    station_inactive = db_bool(conn, "bin_stations", "active", False)
    station_verified = db_bool(conn, "bin_stations", "coordinate_verified", True)
    for index, station_id in enumerate(station_ids, start=1):
        latitude, longitude = coordinates[index - 1]
        offset = (int(digest[index:index + 2], 16) % 9 - 4) * 0.00025
        conn.execute(
            """
            insert into public.bin_stations
              (station_id, name, area, address, latitude, longitude, status, coordinate_verified,
               source, assigned_owner_username, device_id, note, seed_source, active, created_at, updated_at)
            values (%s, %s, %s, %s, %s, %s, 'active', %s, %s, %s, %s, %s, %s, %s, now(), now())
            on conflict (station_id) do update set
              assigned_owner_username = excluded.assigned_owner_username, device_id = excluded.device_id,
              name = excluded.name, area = excluded.area, address = excluded.address,
              latitude = excluded.latitude, longitude = excluded.longitude,
              coordinate_verified = excluded.coordinate_verified, source = excluded.source,
              note = excluded.note, seed_source = excluded.seed_source,
              active = excluded.active, updated_at = now()
            """,
            (
                station_id, f"Điểm rác EcoSort {index}", f"Khu vực {index}",
                f"Điểm thu gom demo số {index}", latitude + offset, longitude - offset,
                station_verified, DEMO_SOURCE, username, device_id,
                "Dữ liệu mô phỏng phục vụ trình bày.",
                DEMO_SOURCE, station_active,
            ),
        )
    conn.execute(
        """
        update public.bin_stations
           set active = %s, updated_at = now()
         where assigned_owner_username = %s and seed_source = %s
           and not (station_id = any(%s))
        """,
        (station_inactive, username, DEMO_SOURCE, station_ids),
    )
    conn.execute(
        """
        update public.bin_stations
           set device_id = %s, source = %s, seed_source = %s, updated_at = now()
         where station_id = any(%s)
        """,
        (device_id, DEMO_SOURCE, DEMO_SOURCE, station_ids),
    )
    return station_ids


def seed_bins(conn: psycopg.Connection[Any], station_id: str, station_number: int) -> None:
    fill_values = ((24, 57, 83), (42, 71, 18), (65, 36, 97))[station_number - 1]
    bin_active = db_bool(conn, "bins", "active", True)
    for (bin_index, command, label), fill_percent in zip(BIN_LABELS, fill_values, strict=True):
        status = "full" if fill_percent >= 95 else "warning" if fill_percent >= 80 else "normal"
        conn.execute(
            """
            insert into public.bins
              (bin_id, station_id, command, bin_index, label, fill_percent, status, active, created_at, updated_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, now(), now())
            on conflict (bin_id) do update set
              label = excluded.label, fill_percent = excluded.fill_percent, status = excluded.status,
              active = excluded.active, updated_at = now()
            """,
            (
                f"{station_id}-{command}", station_id, command, bin_index, label,
                fill_percent, status, bin_active,
            ),
        )


def seed_history(
    conn: psycopg.Connection[Any], username: str, device_id: str, digest: str, count: int
) -> None:
    rows = demo_history_rows(username, device_id, digest, count)
    conn.execute(
        """
        insert into public.history
          (local_history_id, device_id, owner_username, ts, cls_id, cls_name, confidence,
           route_label, bin_index, uart_command, ack_status, rtt_ms, image_available, seed_source)
        select local_history_id, device_id, owner_username, ts, cls_id, cls_name, confidence,
               route_label, bin_index, uart_command, 'ok', rtt_ms, false, %s
          from jsonb_to_recordset(%s::jsonb) as item(
            local_history_id bigint, device_id text, owner_username text, ts timestamptz,
            cls_id integer, cls_name text, confidence numeric, route_label text,
            bin_index integer, uart_command text, rtt_ms integer)
        on conflict (device_id, local_history_id) do update set
          owner_username = excluded.owner_username, ts = excluded.ts, cls_id = excluded.cls_id,
          cls_name = excluded.cls_name, confidence = excluded.confidence,
          route_label = excluded.route_label, bin_index = excluded.bin_index,
          uart_command = excluded.uart_command, rtt_ms = excluded.rtt_ms,
          seed_source = excluded.seed_source
        """,
        (DEMO_SOURCE, json.dumps(rows, ensure_ascii=False)),
    )


def demo_history_rows(
    username: str, device_id: str, digest: str, count: int, now: datetime | None = None
) -> list[dict[str, Any]]:
    base_id = 9_000_000_000 + int(digest[:8], 16) * 100
    current = now or datetime.now(UTC)
    rng = random.Random(int(digest[:16], 16))
    day_offsets = list(range(180))
    day_offsets.extend(rng.randrange(180) for _ in range(max(0, count - 180)))
    rng.shuffle(day_offsets)
    rows: list[dict[str, Any]] = []
    for index in range(count):
        cls_id, cls_name, route_label, bin_index, command = CLASSES[(index + int(digest[8:10], 16)) % len(CLASSES)]
        day = current.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=day_offsets[index])
        timestamp = min(current, day + timedelta(hours=rng.randrange(7, 22), minutes=rng.randrange(60)))
        rows.append({
            "local_history_id": base_id + index,
            "device_id": device_id,
            "owner_username": username,
            "ts": timestamp.isoformat(),
            "cls_id": cls_id,
            "cls_name": cls_name,
            "confidence": round(0.72 + rng.randrange(27) / 100, 4),
            "route_label": route_label,
            "bin_index": bin_index,
            "uart_command": command,
            "rtt_ms": 18 + rng.randrange(23),
        })
    return rows


def seed_schedule_and_alert(
    conn: psycopg.Connection[Any], username: str, station_ids: list[str]
) -> None:
    alert_derived = db_bool(conn, "alerts", "derived", True)
    schedules = (
        ("past", station_ids[0], -7, "completed", "Demo đã thu gom", username),
        ("next", station_ids[1], 2, "scheduled", "Demo lịch sắp tới", ""),
        ("later", station_ids[2], 9, "scheduled", "Demo lịch định kỳ", ""),
    )
    for suffix, station_id, day_delta, status, note, completed_by in schedules:
        conn.execute(
            """
            insert into public.collection_schedules
              (schedule_id, station_id, assigned_owner_username, scheduled_date, window_start,
               window_end, status, note, completed_by, completed_at, created_at, updated_at)
            values (%s, %s, %s, current_date + %s, '08:00', '10:00', %s, %s, %s,
                    case when %s = 'completed' then now() - interval '7 days' else null end,
                    now(), now())
            on conflict (schedule_id) do update set
              scheduled_date = excluded.scheduled_date, status = excluded.status,
              note = excluded.note, completed_by = excluded.completed_by,
              completed_at = excluded.completed_at, updated_at = now()
            """,
            (f"demo-schedule-{suffix}-{station_id}", station_id, username, day_delta,
             status, f"{note}; Seed: {DEMO_SOURCE}", completed_by, status),
        )
    alert_rows = (
        ("full", station_ids[2], "I", "danger", "Thùng đã đầy", "Thùng tái chế đã đầy 97%, cần thu gom.", "open", ""),
        ("resolved", station_ids[0], "I", "warning", "Đã xử lý thùng gần đầy", "Cảnh báo demo đã được xử lý.", "resolved", datetime.now(UTC).isoformat()),
    )
    for suffix, station_id, command, severity, title, message, status, resolved_at in alert_rows:
        conn.execute(
            """
            insert into public.alerts
              (alert_id, station_id, bin_id, device_id, severity, title, message, status, source,
               actor_username, derived, created_at, updated_at, resolved_at)
            values (%s, %s, %s, '', %s, %s, %s, %s, %s, %s, %s, now(), now(), %s)
            on conflict (alert_id) do update set
              severity = excluded.severity, title = excluded.title, message = excluded.message,
              status = excluded.status, resolved_at = excluded.resolved_at, updated_at = now()
            """,
            (f"demo-{suffix}-{station_id}", station_id, f"{station_id}-{command}", severity,
             title, message, status, DEMO_SOURCE, username, alert_derived, resolved_at),
        )


def require_demo_schema(conn: psycopg.Connection[Any]) -> None:
    if not table_exists(conn, "demo_hardware_targets"):
        raise RuntimeError("Run Supabase migrations before seeding demo data.")
    column = conn.execute(
        """select 1 from information_schema.columns
             where table_schema = 'public' and table_name = 'history' and column_name = 'seed_source'"""
    ).fetchone()
    if not column:
        raise RuntimeError("Migration 202606180005_performance_demo_seed.sql is required.")


def verify_seed(conn: psycopg.Connection[Any], users: list[str], expected_history: int) -> None:
    for username in users:
        counts = conn.execute(
            """select
                 (select count(*) from public.bin_stations where assigned_owner_username = %s and seed_source = %s),
                 (select count(*) from public.history where owner_username = %s and seed_source = %s)""",
            (username, DEMO_SOURCE, username, DEMO_SOURCE),
        ).fetchone()
        station_count, history_count = (int(counts[0]), int(counts[1])) if counts else (0, 0)
        if station_count < 3 or history_count < expected_history:
            raise RuntimeError(
                f"Seed verification failed for {username}: stations={station_count}, history={history_count}"
            )
        print(f"Verified {username}: {station_count} stations, {history_count} demo history rows")


def table_exists(conn: psycopg.Connection[Any], table: str) -> bool:
    row = conn.execute("select to_regclass(%s)", (f"public.{table}",)).fetchone()
    return bool(row and row[0])


def function_exists(conn: psycopg.Connection[Any], function: str) -> bool:
    row = conn.execute("select to_regprocedure(%s)", (f"public.{function}(text)",)).fetchone()
    return bool(row and row[0])


def db_bool(
    conn: psycopg.Connection[Any], table: str, column: str, value: bool
) -> bool | int:
    row = conn.execute(
        """select data_type from information_schema.columns
             where table_schema = 'public' and table_name = %s and column_name = %s""",
        (table, column),
    ).fetchone()
    if row and str(row[0]) in {"integer", "bigint", "smallint", "numeric"}:
        return 1 if value else 0
    return value


if __name__ == "__main__":
    raise SystemExit(main())
