"""Start the Trash Sorter Pro local FastAPI agent."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _agent_host_port() -> tuple[str, int]:
    host = os.getenv("TRASH_SORTER_AGENT_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = _env_port("TRASH_SORTER_AGENT_PORT", 8765)
    return host, port


def _env_port(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value < 1 or value > 65535:
        return default
    return value


def main() -> None:
    from app.utils.local_web import apply_local_auth_environment

    apply_local_auth_environment(allow_dev_defaults=True)

    from app.agent.api import create_app

    host, port = _agent_host_port()
    log_level = os.getenv("TRASH_SORTER_AGENT_LOG_LEVEL", "info").strip() or "info"
    uvicorn.run(create_app(), host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()
