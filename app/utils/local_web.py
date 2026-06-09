"""Start and open the local web dashboard from the desktop app."""

from __future__ import annotations

import http.client
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from app.utils.logging import logger
from app.utils.paths import auth_db_path

AGENT_PORT = 8765
WEB_PORT = 3000
AGENT_URL = f"http://127.0.0.1:{AGENT_PORT}"
WEB_URL = f"http://127.0.0.1:{WEB_PORT}/?tab=live"
AUTH_DEV_DEFAULTS_ENV = "TRASH_SORTER_AUTH_DEV_DEFAULTS"
AUTH_DB_ENV = "TRASH_SORTER_AUTH_DB"
AUTH_DATABASE_URL_ENV = "TRASH_SORTER_AUTH_DATABASE_URL"
DATABASE_URL_ENV = "DATABASE_URL"
BOOTSTRAP_ADMIN_USERNAME_ENV = "TRASH_SORTER_BOOTSTRAP_ADMIN_USERNAME"
BOOTSTRAP_ADMIN_PASSWORD_ENV = "TRASH_SORTER_BOOTSTRAP_ADMIN_PASSWORD"
NEXT_PUBLIC_AGENT_URL_ENV = "NEXT_PUBLIC_AGENT_URL"
LOCAL_ENV_FILES = (".env", ".env.local")


@dataclass(frozen=True)
class LocalWebResult:
    ok: bool
    message: str
    url: str = WEB_URL


def ensure_local_web_stack() -> LocalWebResult:
    root = _project_root()
    if root is None:
        return LocalWebResult(
            ok=False,
            message="Không tìm thấy thư mục project để bật web dashboard.",
        )

    if not _port_listening(AGENT_PORT):
        agent = root / "scripts" / "run_agent.py"
        if not agent.exists():
            return LocalWebResult(ok=False, message="Không tìm thấy scripts/run_agent.py.")
        _start_hidden([_python_executable(), str(agent)], cwd=root, env_overrides=_agent_env(root))
        logger.info("local web launcher started agent")

    if not _wait_http(f"{AGENT_URL}/api/health", timeout_s=20):
        return LocalWebResult(ok=False, message="Agent chưa sẵn sàng ở cổng 8765.")

    if not _port_listening(WEB_PORT):
        web_root = root / "web"
        if not (web_root / "package.json").exists():
            return LocalWebResult(ok=False, message="Không tìm thấy thư mục web/package.json.")
        _start_hidden(
            [_npm_executable(), "run", "dev"],
            cwd=web_root,
            env_overrides={NEXT_PUBLIC_AGENT_URL_ENV: AGENT_URL},
        )
        logger.info("local web launcher started Next.js web")

    if not _wait_http(f"http://127.0.0.1:{WEB_PORT}/?tab=live", timeout_s=35):
        return LocalWebResult(ok=False, message="Web chưa sẵn sàng ở cổng 3000.")

    return LocalWebResult(ok=True, message="Web dashboard đã sẵn sàng. Vui lòng đăng nhập.", url=WEB_URL)


def _agent_env(root: Path) -> dict[str, str]:
    env = _local_env(root)
    if not _auth_explicitly_configured(env):
        env[AUTH_DEV_DEFAULTS_ENV] = "1"
    return env


def _auth_explicitly_configured(extra_env: dict[str, str] | None = None) -> bool:
    extra_env = extra_env or {}
    for key in (
        AUTH_DEV_DEFAULTS_ENV,
        AUTH_DB_ENV,
        AUTH_DATABASE_URL_ENV,
        DATABASE_URL_ENV,
        BOOTSTRAP_ADMIN_USERNAME_ENV,
        BOOTSTRAP_ADMIN_PASSWORD_ENV,
    ):
        if extra_env.get(key, "").strip() or os.getenv(key, "").strip():
            return True
    try:
        return auth_db_path().exists()
    except OSError:
        return False


def _local_env(root: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for name in LOCAL_ENV_FILES:
        env.update(_read_env_file(root / name))
    return env


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def _project_root() -> Path | None:
    candidates = [
        Path.cwd(),
        Path(__file__).resolve().parents[2],
        Path(sys.executable).resolve().parent,
        Path(sys.executable).resolve().parent.parent,
    ]
    for base in candidates:
        current = base.resolve()
        for path in (current, *current.parents):
            found = _project_root_at(path)
            if found is not None:
                return found
            for child_name in ("trash-sorter-v2", "TrashSorterPro", "Trash Sorter Pro"):
                found = _project_root_at(path / child_name)
                if found is not None:
                    return found
    return None


def _project_root_at(path: Path) -> Path | None:
    if (path / "web" / "package.json").exists() and (path / "scripts" / "run_agent.py").exists():
        return path
    return None


def _python_executable() -> str:
    root = _project_root()
    if root is not None:
        venv_python = root / ".venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            return str(venv_python)
    return sys.executable if not getattr(sys, "frozen", False) else "python"


def _npm_executable() -> str:
    return "npm.cmd" if sys.platform == "win32" else "npm"


def _port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _wait_http(url: str, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _http_ok(url):
            return True
        time.sleep(0.5)
    return False


def _http_ok(url: str) -> bool:
    try:
        _, rest = url.split("://", 1)
        host_port, path = rest.split("/", 1)
        host, port_s = host_port.rsplit(":", 1)
        conn = http.client.HTTPConnection(host, int(port_s), timeout=2)
        try:
            conn.request("GET", f"/{path}")
            res = conn.getresponse()
            res.read(256)
            return 200 <= res.status < 500
        finally:
            conn.close()
    except (OSError, ValueError, http.client.HTTPException):
        return False


def _start_hidden(command: list[str], *, cwd: Path, env_overrides: dict[str, str] | None = None) -> None:
    kwargs: dict = {
        "cwd": str(cwd),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if env_overrides:
        env = os.environ.copy()
        env.update(env_overrides)
        kwargs["env"] = env
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command, **kwargs)
