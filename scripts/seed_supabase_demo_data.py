"""Seed persistent teacher-demo data for every active User account."""

from __future__ import annotations

import argparse
import hashlib
import os
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
)
BIN_LABELS = ((1, "O", "Hữu cơ"), (2, "R", "Vô cơ"), (3, "I", "Tái chế"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write demo data. Default is dry-run.")
    parser.add_argument("--history-count", type=int, default=60)
    args = parser.parse_args()
    database_url = next((os.getenv(name, "").strip() for name in DATABASE_ENV_NAMES if os.getenv(name, "").strip()), "")
    if not database_url:
        raise SystemExit(f"Set one of: {', '.join(DATABASE_ENV_NAMES)}")

    with psycopg.connect(database_url, autocommit=False, prepare_threshold=None) as conn:
        users = active_usernames(conn)
        print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
        print(f"Users: {len(users)}")
        print(f"Planned: {len(users) * 3} stations, {len(users) * 9} bins, "
              f"{len(users) * max(1, args.history_count)} history rows")
        if not args.apply:
            conn.rollback()
            return 0
        ensure_demo_target_table(conn)
        for username in users:
            seed_user(conn, username, max(1, args.history_count))
        conn.commit()
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
    if function_exists(conn, "ensure_user_map_stations_if_available"):
        conn.execute("select public.ensure_user_map_stations_if_available(%s)", (username,))
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
    rows = conn.execute(
        """
        select station_id from public.bin_stations
         where assigned_owner_username = %s
           and coalesce(active::text, 'true') not in ('0', 'false', 'f', 'no')
         order by created_at, station_id limit 3
        """,
        (username,),
    ).fetchall()
    station_ids = [str(row[0]) for row in rows]
    coordinates = ((10.8020001, 106.7406138), (10.8276722, 106.7215390), (10.8502385, 106.7541974))
    station_active = db_bool(conn, "bin_stations", "active", True)
    station_verified = db_bool(conn, "bin_stations", "coordinate_verified", True)
    while len(station_ids) < 3:
        index = len(station_ids) + 1
        station_id = f"user-{digest[:12]}-{index}"
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
        station_ids.append(station_id)
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
    fill_values = ((24, 57, 83), (42, 71, 18), (65, 36, 88))[station_number - 1]
    bin_active = db_bool(conn, "bins", "active", True)
    for (bin_index, command, label), fill_percent in zip(BIN_LABELS, fill_values, strict=True):
        status = "warning" if fill_percent >= 80 else "normal"
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
    base_id = 9_000_000_000 + int(digest[:8], 16) * 100
    now = datetime.now(UTC)
    for index in range(count):
        cls_id, cls_name, route_label, bin_index, command = CLASSES[(index + int(digest[8:10], 16)) % len(CLASSES)]
        timestamp = now - timedelta(days=(index * 7) % 180, hours=(index * 5) % 24)
        confidence = 0.72 + ((index * 13 + int(digest[10:12], 16)) % 26) / 100
        conn.execute(
            """
            insert into public.history
              (local_history_id, device_id, owner_username, ts, cls_id, cls_name, confidence,
               route_label, bin_index, uart_command, ack_status, rtt_ms, image_available)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ok', %s, false)
            on conflict (device_id, local_history_id) do update set
              owner_username = excluded.owner_username, ts = excluded.ts, confidence = excluded.confidence
            """,
            (
                base_id + index, device_id, username, timestamp, cls_id, cls_name,
                confidence, route_label, bin_index, command, 18 + index % 23,
            ),
        )


def seed_schedule_and_alert(
    conn: psycopg.Connection[Any], username: str, station_ids: list[str]
) -> None:
    station_id = station_ids[0]
    alert_derived = db_bool(conn, "alerts", "derived", True)
    conn.execute(
        """
        insert into public.collection_schedules
          (schedule_id, station_id, assigned_owner_username, scheduled_date, window_start,
           window_end, status, note, completed_by, created_at, updated_at)
        values (%s, %s, %s, current_date + 2, '08:00', '10:00', 'scheduled', %s, '', now(), now())
        on conflict (schedule_id) do update set scheduled_date = excluded.scheduled_date, updated_at = now()
        """,
        (f"demo-schedule-{station_id}", station_id, username, f"Seed: {DEMO_SOURCE}"),
    )
    conn.execute(
        """
        insert into public.alerts
          (alert_id, station_id, bin_id, device_id, severity, title, message, status, source,
           actor_username, derived, created_at, updated_at, resolved_at)
        values (%s, %s, %s, '', 'warning', 'Thùng gần đầy', %s, 'open', %s, %s, %s, now(), now(), '')
        on conflict (alert_id) do update set message = excluded.message, status = 'open', updated_at = now()
        """,
        (
            f"demo-warning-{station_id}", station_id, f"{station_id}-I",
            "Thùng tái chế đang ở mức 83%, cần theo dõi.", DEMO_SOURCE, username,
            alert_derived,
        ),
    )


def ensure_demo_target_table(conn: psycopg.Connection[Any]) -> None:
    conn.execute(
        """
        create table if not exists public.demo_hardware_targets (
          owner_username text primary key,
          station_id text not null references public.bin_stations(station_id) on delete cascade,
          bin_id text not null default '', bin_index integer not null check (bin_index between 1 and 3),
          selected_by text not null default '', selected_at timestamptz not null default now(),
          last_applied_at timestamptz, last_percent numeric(5,2), active boolean not null default true
        )
        """
    )


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
