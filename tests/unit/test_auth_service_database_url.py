from app.agent.auth_service import configured_auth_database_url, normalize_database_url


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
