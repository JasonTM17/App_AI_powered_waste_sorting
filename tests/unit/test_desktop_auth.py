from pathlib import Path

from app.agent.auth_service import AuthService
from app.ui.desktop_auth import authenticate_desktop_admin


def _service_factory(db_path: Path):
    return lambda: AuthService(db_path=db_path)


def test_desktop_auth_allows_admin_account(tmp_path):
    db_path = tmp_path / "auth.db"
    service = AuthService(db_path=db_path)
    service.create_account("owner", "owner-pass-123", "admin")

    result = authenticate_desktop_admin(
        "owner",
        "owner-pass-123",
        service_factory=_service_factory(db_path),
    )

    assert result.ok is True
    assert result.identity is not None
    assert result.identity.role == "admin"
    assert result.token


def test_desktop_auth_rejects_user_role_and_revokes_session(tmp_path):
    db_path = tmp_path / "auth.db"
    service = AuthService(db_path=db_path)
    service.create_account("viewer", "viewer-pass-123", "user")

    result = authenticate_desktop_admin(
        "viewer",
        "viewer-pass-123",
        service_factory=_service_factory(db_path),
    )

    assert result.ok is False
    assert "Admin" in result.message
    assert result.token == ""


def test_desktop_auth_reports_missing_accounts_as_failed_login(tmp_path):
    db_path = tmp_path / "auth.db"

    result = authenticate_desktop_admin(
        "owner",
        "owner-pass-123",
        service_factory=_service_factory(db_path),
    )

    assert result.ok is False
    assert "Sai tài khoản hoặc mật khẩu" in result.message


def test_desktop_auth_can_require_shared_sql_database(tmp_path):
    db_path = tmp_path / "auth.db"
    service = AuthService(db_path=db_path)
    service.create_account("owner", "owner-pass-123", "admin")

    result = authenticate_desktop_admin(
        "owner",
        "owner-pass-123",
        service_factory=_service_factory(db_path),
        require_shared_database=True,
    )

    assert result.ok is False
    assert "TRASH_SORTER_AUTH_DATABASE_URL" in result.message


def test_desktop_auth_identifies_postgres_password_mismatch(tmp_path):
    db_path = tmp_path / "auth.db"
    service = AuthService(db_path=db_path)
    service.create_account("owner", "owner-pass-123", "admin")
    service.database_url = "postgresql://configured"

    result = authenticate_desktop_admin(
        "owner",
        "wrong-pass-123",
        service_factory=lambda: service,
    )

    assert result.ok is False
    assert "PostgreSQL đã kết nối" in result.message
    assert "mật khẩu kết nối DB" in result.message


def test_desktop_auth_uses_latest_password_from_account_database(tmp_path):
    db_path = tmp_path / "auth.db"
    service = AuthService(db_path=db_path)
    service.create_account("owner", "old-owner-pass-123", "admin")
    assert service.set_password("owner", "new-owner-pass-456", revoke_sessions=True)

    old_result = authenticate_desktop_admin(
        "owner",
        "old-owner-pass-123",
        service_factory=_service_factory(db_path),
    )
    new_result = authenticate_desktop_admin(
        "owner",
        "new-owner-pass-456",
        service_factory=_service_factory(db_path),
    )

    assert old_result.ok is False
    assert new_result.ok is True
