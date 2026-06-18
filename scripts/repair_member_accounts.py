"""Repair legacy member account names and ownership references."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.auth_service import AuthService
from app.agent.auth_tables import accounts, sessions
from app.utils.local_web import apply_local_auth_environment
from app.utils.paths import db_path, operations_db_path

MEMBERS: dict[str, str] = {
    "nguyen-son": "Nguyễn Sơn",
    "ngoc-quyen": "Ngọc Quyên",
    "gia-kiet": "Gia Kiệt",
    "minh-huy": "Minh Huy",
    "hong-thuy": "Hồng Thủy",
}

LEGACY_ALIASES: dict[str, tuple[str, ...]] = {
    "nguyen-son": ("Nguyễn Sơn", "Nguy?n S?n"),
    "ngoc-quyen": ("Ngọc Quyên", "Ng?c Quy?n"),
    "gia-kiet": ("Gia Kiệt", "Gia Ki?t"),
    "minh-huy": ("Minh Huy",),
    "hong-thuy": ("Hồng Thủy", "H?ng Th?y"),
}

OPERATIONS_USERNAME_COLUMNS = {
    "devices": ("owner_username",),
    "bin_stations": ("assigned_owner_username",),
    "collection_schedules": ("assigned_owner_username", "completed_by"),
    "collection_events": ("actor_username",),
    "alerts": ("actor_username",),
    "device_issues": ("reporter_username",),
}

HISTORY_USERNAME_COLUMNS = {
    "detections": ("owner_username",),
}


@dataclass
class RepairSummary:
    display_names_updated: list[str] = field(default_factory=list)
    legacy_disabled: list[str] = field(default_factory=list)
    legacy_purged: list[str] = field(default_factory=list)
    refs_migrated: dict[str, int] = field(default_factory=dict)
    skipped_active_legacy: list[str] = field(default_factory=list)

    def print(self, *, apply: bool) -> None:
        mode = "apply" if apply else "dry-run"
        print(f"repair mode: {mode}")
        _print_list("display names to update", self.display_names_updated)
        _print_list("legacy accounts to disable", self.legacy_disabled)
        _print_list("legacy accounts to purge", self.legacy_purged)
        _print_list("active legacy accounts skipped from purge", self.skipped_active_legacy)
        if self.refs_migrated:
            print("ownership refs to migrate:")
            for key, count in sorted(self.refs_migrated.items()):
                print(f"  {key}: {count}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair EcoSort demo member accounts.")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Default is dry-run.")
    parser.add_argument(
        "--purge-disabled-legacy",
        action="store_true",
        help="Delete disabled known legacy auth rows after migrating ownership references.",
    )
    args = parser.parse_args()

    apply_local_auth_environment(allow_dev_defaults=True)
    service = AuthService()
    summary = repair_member_accounts(
        service,
        apply=args.apply,
        purge_disabled_legacy=args.purge_disabled_legacy,
    )
    summary.print(apply=args.apply)
    if not args.apply:
        print("No changes written. Re-run with --apply to repair.")
    return 0


def repair_member_accounts(
    service: AuthService,
    *,
    apply: bool,
    purge_disabled_legacy: bool,
) -> RepairSummary:
    service.ensure_ready()
    summary = RepairSummary()
    alias_to_canonical = _alias_to_canonical()

    _repair_auth_accounts(service, summary, apply=apply, purge_disabled_legacy=purge_disabled_legacy)
    _migrate_sqlite_refs(
        operations_db_path(),
        OPERATIONS_USERNAME_COLUMNS,
        alias_to_canonical,
        summary,
        apply=apply,
        label="operations",
    )
    _migrate_sqlite_refs(
        db_path(),
        HISTORY_USERNAME_COLUMNS,
        alias_to_canonical,
        summary,
        apply=apply,
        label="history",
    )
    return summary


def _repair_auth_accounts(
    service: AuthService,
    summary: RepairSummary,
    *,
    apply: bool,
    purge_disabled_legacy: bool,
) -> None:
    with service._engine.begin() as conn:
        rows = conn.execute(select(accounts)).mappings().all()
        by_username = {str(row["username"]): row for row in rows}

        for username, display_name in MEMBERS.items():
            row = by_username.get(username)
            if row is not None and str(row.get("display_name") or "") != display_name:
                summary.display_names_updated.append(username)
                if apply:
                    conn.execute(
                        accounts.update()
                        .where(accounts.c.username == username)
                        .values(display_name=display_name)
                    )

        for aliases in LEGACY_ALIASES.values():
            for alias in aliases:
                row = by_username.get(alias)
                if row is None:
                    continue
                account_id = int(row["id"])
                is_active = bool(int(row["is_active"]))
                if is_active:
                    summary.legacy_disabled.append(alias)
                    summary.skipped_active_legacy.append(alias)
                    if apply:
                        conn.execute(
                            accounts.update()
                            .where(accounts.c.id == account_id)
                            .values(is_active=0)
                        )
                        conn.execute(
                            sessions.update()
                            .where(sessions.c.account_id == account_id)
                            .where(sessions.c.revoked_at.is_(None))
                            .values(revoked_at="revoked-by-member-repair")
                        )
                    continue
                if purge_disabled_legacy:
                    summary.legacy_purged.append(alias)
                    if apply:
                        conn.execute(sessions.delete().where(sessions.c.account_id == account_id))
                        conn.execute(accounts.delete().where(accounts.c.id == account_id))


def _migrate_sqlite_refs(
    path: Path,
    table_columns: dict[str, tuple[str, ...]],
    alias_to_canonical: dict[str, str],
    summary: RepairSummary,
    *,
    apply: bool,
    label: str,
) -> None:
    if not path.exists():
        return
    with sqlite3.connect(path) as conn:
        existing_tables = {
            str(row[0])
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        for table, columns in table_columns.items():
            if table not in existing_tables:
                continue
            existing_columns = {
                str(row[1])
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for column in columns:
                if column not in existing_columns:
                    continue
                for alias, canonical in alias_to_canonical.items():
                    count = int(
                        conn.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE {column} = ?",
                            (alias,),
                        ).fetchone()[0]
                    )
                    if count == 0:
                        continue
                    key = f"{label}.{table}.{column}:{alias}->{canonical}"
                    summary.refs_migrated[key] = count
                    if apply:
                        conn.execute(
                            f"UPDATE {table} SET {column} = ? WHERE {column} = ?",
                            (canonical, alias),
                        )
        if not apply:
            conn.rollback()


def _alias_to_canonical() -> dict[str, str]:
    out: dict[str, str] = {}
    for canonical, aliases in LEGACY_ALIASES.items():
        for alias in aliases:
            out[alias] = canonical
    return out


def _print_list(title: str, values: list[str]) -> None:
    if not values:
        return
    print(f"{title}:")
    for value in values:
        print(f"  {value}")


if __name__ == "__main__":
    raise SystemExit(main())
