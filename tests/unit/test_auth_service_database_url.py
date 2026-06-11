from app.agent import auth_service as auth_service_module
from app.agent.auth_service import (
    AuthService,
    configured_auth_database_url,
    create_database_engine,
    normalize_database_url,
)


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
