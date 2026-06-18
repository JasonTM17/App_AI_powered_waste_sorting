import sqlite3

from app.agent.auth_service import AuthService
from scripts.repair_member_accounts import repair_member_accounts


def test_repair_member_accounts_dry_run_and_apply(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("TRASH_SORTER_AUTH_DB", str(tmp_path / "auth.db"))
    service = AuthService()
    service.create_account("nguyen-son", "nguyen-son-pass-123", "user", display_name="Nguyen Son")
    service.create_account("Nguy?n S?n", "legacy-bad-pass-123", "user")
    service.set_active("Nguy?n S?n", False)
    service.create_account("Nguyễn Sơn", "legacy-good-pass-123", "user")
    service.set_active("Nguyễn Sơn", False)

    operations_db = tmp_path / "TrashSorter" / "operations.db"
    operations_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(operations_db) as conn:
        conn.execute("CREATE TABLE devices (owner_username TEXT)")
        conn.execute("INSERT INTO devices VALUES (?)", ("Nguy?n S?n",))
        conn.execute("CREATE TABLE bin_stations (assigned_owner_username TEXT)")
        conn.execute("INSERT INTO bin_stations VALUES (?)", ("Nguyễn Sơn",))

    summary = repair_member_accounts(service, apply=False, purge_disabled_legacy=True)
    assert "nguyen-son" in summary.display_names_updated
    assert "Nguy?n S?n" in summary.legacy_purged
    assert "Nguyễn Sơn" in summary.legacy_purged
    with sqlite3.connect(operations_db) as conn:
        assert conn.execute("SELECT owner_username FROM devices").fetchone()[0] == "Nguy?n S?n"

    repair_member_accounts(service, apply=True, purge_disabled_legacy=True)
    accounts = {str(row["username"]): row for row in service.list_accounts()}
    assert accounts["nguyen-son"]["display_name"] == "Nguyễn Sơn"
    assert "Nguy?n S?n" not in accounts
    assert "Nguyễn Sơn" not in accounts
    with sqlite3.connect(operations_db) as conn:
        assert conn.execute("SELECT owner_username FROM devices").fetchone()[0] == "nguyen-son"
        assert conn.execute("SELECT assigned_owner_username FROM bin_stations").fetchone()[0] == "nguyen-son"
