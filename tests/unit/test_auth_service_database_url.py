from sqlalchemy import create_engine, inspect, text

from app.agent import auth_service as auth_service_module
from app.agent.auth_service import (
    AuthService,
    account_auth_is_configured,
    configured_auth_database_url,
    create_database_engine,
    normalize_database_url,
)
from app.agent.auth_tables import metadata


def test_normalize_postgres_database_url_uses_psycopg_driver():
    assert (
        normalize_database_url("postgres://user:pass@localhost:5432/trash")
        == "postgresql+psycopg://user:pass@localhost:5432/trash"
    )
    assert (
        normalize_database_url("postgresql://user:pass@localhost:5432/trash")
        == "postgresql+psycopg://user:pass@localhost:5432/trash"
    )


def test_configured_auth_database_url_prefers_auth_specific_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://global:pass@localhost/app")
    monkeypatch.setenv("TRASH_SORTER_AUTH_DATABASE_URL", "postgresql://auth:pass@localhost/auth")

    assert configured_auth_database_url() == "postgresql+psycopg://auth:pass@localhost/auth"


def test_postgres_engine_uses_supabase_pooler_safe_options(monkeypatch):
    captured: dict[str, object] = {}
    fake_engine = object()

    def fake_create_engine(database_url: str, **kwargs: object):
        captured["database_url"] = database_url
        captured.update(kwargs)
        return fake_engine

    monkeypatch.setattr(auth_service_module, "create_engine", fake_create_engine)

    assert create_database_engine("postgresql+psycopg://user:pass@localhost/postgres") is fake_engine
    assert captured["database_url"] == "postgresql+psycopg://user:pass@localhost/postgres"
    assert captured["pool_pre_ping"] is True
    assert captured["pool_size"] == 2
    assert captured["max_overflow"] == 3
    assert captured["pool_timeout"] == 5
    assert captured["pool_recycle"] == 1800
    assert captured["connect_args"] == {"prepare_threshold": None}


def test_auth_service_constructor_defers_schema_bootstrap(tmp_path):
    db_path = tmp_path / "auth.db"

    AuthService(db_path=db_path)

    assert not db_path.exists()


def test_account_auth_configured_short_circuits_when_database_url_is_set(monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_AUTH_DATABASE_URL", "postgresql://auth:pass@localhost/auth")

    def fail_has_accounts(self):
        raise AssertionError("has_accounts should not run just to detect configured auth")

    monkeypatch.setattr(AuthService, "has_accounts", fail_has_accounts)

    assert account_auth_is_configured() is True


def test_remote_auth_schema_probe_skips_create_all_when_schema_exists(monkeypatch):
    engine = create_engine("sqlite:///:memory:", future=True)
    metadata.create_all(engine)
    database_url = "postgresql+psycopg://user:pass@localhost/auth_probe_test"

    monkeypatch.setattr(auth_service_module, "_engine_for_auth_store", lambda *_: engine)

    def fail_create_all(_engine):
        raise AssertionError("metadata.create_all should be skipped for ready remote schema")

    monkeypatch.setattr(auth_service_module.metadata, "create_all", fail_create_all)

    AuthService(database_url=database_url).ensure_ready()


def test_remote_auth_schema_adds_avatar_path_to_legacy_accounts(monkeypatch):
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE accounts ("
                "id INTEGER PRIMARY KEY, username VARCHAR NOT NULL UNIQUE, "
                "display_name VARCHAR DEFAULT '', role VARCHAR NOT NULL, "
                "password_hash VARCHAR NOT NULL, salt VARCHAR NOT NULL, "
                "iterations INTEGER NOT NULL, is_active INTEGER DEFAULT 1, "
                "password_default INTEGER DEFAULT 0, created_at VARCHAR NOT NULL, "
                "updated_at VARCHAR NOT NULL, last_login_at VARCHAR)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE sessions ("
                "id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, "
                "token_hash VARCHAR NOT NULL UNIQUE, created_at VARCHAR NOT NULL, "
                "expires_at VARCHAR NOT NULL, revoked_at VARCHAR, client_label VARCHAR DEFAULT '')"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE chat_usage ("
                "id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, period VARCHAR NOT NULL, "
                "used INTEGER DEFAULT 0, updated_at VARCHAR NOT NULL)"
            )
        )
    database_url = "postgresql+psycopg://user:pass@localhost/auth_legacy_test"
    monkeypatch.setattr(auth_service_module, "_engine_for_auth_store", lambda *_: engine)

    AuthService(database_url=database_url).ensure_ready()

    with engine.begin() as conn:
        columns = {str(row["name"]) for row in inspect(conn).get_columns("accounts")}
    assert "avatar_path" in columns
