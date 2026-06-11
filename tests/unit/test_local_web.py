import os
from pathlib import Path

from app.utils import local_web


def _project_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    scripts = root / "scripts"
    web = root / "web"
    scripts.mkdir(parents=True)
    web.mkdir()
    (scripts / "run_agent.py").write_text("", encoding="utf-8")
    (web / "package.json").write_text("{}", encoding="utf-8")
    return root


def _clear_auth_env(monkeypatch):
    for key in (
        local_web.AUTH_DEV_DEFAULTS_ENV,
        local_web.AUTH_DB_ENV,
        local_web.AUTH_DATABASE_URL_ENV,
        local_web.DATABASE_URL_ENV,
        local_web.BOOTSTRAP_ADMIN_USERNAME_ENV,
        local_web.BOOTSTRAP_ADMIN_PASSWORD_ENV,
    ):
        monkeypatch.delenv(key, raising=False)


def _patch_successful_launch(monkeypatch, root: Path):
    started = []

    def start_hidden(command, *, cwd, env_overrides=None):
        started.append(
            {
                "command": command,
                "cwd": cwd,
                "env_overrides": env_overrides or {},
            }
        )

    monkeypatch.setattr(local_web, "_project_root", lambda: root)
    monkeypatch.setattr(local_web, "_port_listening", lambda _port: False)
    monkeypatch.setattr(local_web, "_wait_http", lambda _url, timeout_s: True)
    monkeypatch.setattr(local_web, "_python_executable", lambda: "python")
    monkeypatch.setattr(local_web, "_npm_executable", lambda: "npm")
    monkeypatch.setattr(local_web, "_start_hidden", start_hidden)
    return started


def test_desktop_launcher_injects_dev_auth_defaults_for_unconfigured_local_launch(
    tmp_path, monkeypatch
):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    root = _project_root(tmp_path)
    started = _patch_successful_launch(monkeypatch, root)

    result = local_web.ensure_local_web_stack()

    assert result.ok is True
    assert "đăng nhập" in result.message
    assert started == [
        {
            "command": ["python", str(root / "scripts" / "run_agent.py")],
            "cwd": root,
            "env_overrides": {local_web.AUTH_DEV_DEFAULTS_ENV: "1"},
        },
        {
            "command": ["npm", "run", "dev"],
            "cwd": root / "web",
            "env_overrides": {local_web.NEXT_PUBLIC_AGENT_URL_ENV: local_web.AGENT_URL},
        },
    ]


def test_desktop_launcher_preserves_explicit_production_auth_env(tmp_path, monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv(local_web.BOOTSTRAP_ADMIN_USERNAME_ENV, "owner")
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    root = _project_root(tmp_path)
    started = _patch_successful_launch(monkeypatch, root)

    result = local_web.ensure_local_web_stack()

    assert result.ok is True
    assert started[0]["env_overrides"] == {}


def test_desktop_launcher_preserves_postgres_auth_env(tmp_path, monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv(local_web.AUTH_DATABASE_URL_ENV, "postgresql://user:pass@db.local/trash")
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    root = _project_root(tmp_path)
    started = _patch_successful_launch(monkeypatch, root)

    result = local_web.ensure_local_web_stack()

    assert result.ok is True
    assert started[0]["env_overrides"] == {}


def test_desktop_launcher_keeps_existing_auth_db(tmp_path, monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    auth_db = local_web.auth_db_path()
    auth_db.parent.mkdir(parents=True, exist_ok=True)
    auth_db.touch()
    root = _project_root(tmp_path)
    started = _patch_successful_launch(monkeypatch, root)

    result = local_web.ensure_local_web_stack()

    assert result.ok is True
    assert started[0]["env_overrides"] == {}


def test_desktop_launcher_loads_local_agent_env_file(tmp_path, monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    root = _project_root(tmp_path)
    (root / ".env.local").write_text(
        "\n".join(
            [
                "DEEPSEEK_API_KEY=deepseek-local-key",
                "DEEPSEEK_MODEL=deepseek-v4-flash",
                "TRASH_SORTER_AUTH_DATABASE_URL=postgresql://user:pass@localhost/trash",
            ]
        ),
        encoding="utf-8",
    )
    started = _patch_successful_launch(monkeypatch, root)

    result = local_web.ensure_local_web_stack()

    assert result.ok is True
    assert started[0]["env_overrides"] == {
        "DEEPSEEK_API_KEY": "deepseek-local-key",
        "DEEPSEEK_MODEL": "deepseek-v4-flash",
        local_web.AUTH_DATABASE_URL_ENV: "postgresql://user:pass@localhost/trash",
    }


def test_desktop_login_applies_same_local_auth_env_file_as_web(tmp_path, monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    root = _project_root(tmp_path)
    auth_db = tmp_path / "shared-auth.db"
    (root / ".env.local").write_text(
        f"{local_web.AUTH_DB_ENV}={auth_db}\n"
        f"{local_web.BOOTSTRAP_ADMIN_USERNAME_ENV}=owner\n"
        f"{local_web.BOOTSTRAP_ADMIN_PASSWORD_ENV}=owner-pass-123\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(local_web, "_project_root", lambda: root)

    try:
        applied = local_web.apply_local_auth_environment(allow_dev_defaults=True)

        assert applied[local_web.AUTH_DB_ENV] == str(auth_db)
        assert applied[local_web.BOOTSTRAP_ADMIN_USERNAME_ENV] == "owner"
        assert applied[local_web.BOOTSTRAP_ADMIN_PASSWORD_ENV] == "owner-pass-123"
        assert local_web.AUTH_DEV_DEFAULTS_ENV not in applied
    finally:
        for key in local_web.AUTH_ENV_KEYS:
            os.environ.pop(key, None)


def test_explicit_sqlite_auth_db_blocks_database_url_from_local_env(tmp_path, monkeypatch):
    _clear_auth_env(monkeypatch)
    root = _project_root(tmp_path)
    explicit_db = tmp_path / "playwright-auth.db"
    monkeypatch.setenv(local_web.AUTH_DB_ENV, str(explicit_db))
    (root / ".env.local").write_text(
        "\n".join(
            [
                "TRASH_SORTER_AUTH_DATABASE_URL=postgresql://prod.example/trash",
                "DEEPSEEK_API_KEY=local-ai-key",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(local_web, "_project_root", lambda: root)

    applied = local_web.apply_local_auth_environment(allow_dev_defaults=True)

    assert applied == {}
    assert os.environ[local_web.AUTH_DB_ENV] == str(explicit_db)
    assert local_web.AUTH_DATABASE_URL_ENV not in os.environ


def test_agent_env_keeps_explicit_sqlite_store_and_non_auth_file_values(
    tmp_path, monkeypatch
):
    _clear_auth_env(monkeypatch)
    root = _project_root(tmp_path)
    explicit_db = tmp_path / "playwright-auth.db"
    monkeypatch.setenv(local_web.AUTH_DB_ENV, str(explicit_db))
    (root / ".env.local").write_text(
        "\n".join(
            [
                "TRASH_SORTER_AUTH_DATABASE_URL=postgresql://prod.example/trash",
                "DEEPSEEK_API_KEY=local-ai-key",
            ]
        ),
        encoding="utf-8",
    )

    env = local_web._agent_env(root)

    assert local_web.AUTH_DATABASE_URL_ENV not in env
    assert local_web.AUTH_DB_ENV not in env
    assert env["DEEPSEEK_API_KEY"] == "local-ai-key"
