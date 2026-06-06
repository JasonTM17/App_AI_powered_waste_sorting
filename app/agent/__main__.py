"""Run the local web agent with `python -m app.agent`."""

from __future__ import annotations

import uvicorn

from app.agent.api import create_app


def main() -> None:
    uvicorn.run(create_app(), host="127.0.0.1", port=8765, log_level="info")


if __name__ == "__main__":
    main()
