"""Structured JSON logging via loguru.

Production-ready setup that survives PyInstaller --noconsole builds where
``sys.stderr`` and ``sys.stdout`` can be ``None``.
"""

from __future__ import annotations

import contextlib
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

from app.utils.paths import logs_dir


def _resolve_log_dir() -> Path:
    try:
        d = logs_dir()
        d.mkdir(parents=True, exist_ok=True)
        return d
    except Exception:
        # last-resort fallback next to the executable / cwd
        fallback = Path.cwd() / "logs"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _resolve_log_file(custom: str | Path | None = None) -> Path:
    if custom:
        p = Path(custom)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass
    return _resolve_log_dir() / f"app-{datetime.now():%Y-%m-%d}.log"


def _has_console_stream() -> bool:
    """True if stderr is a usable stream.

    Under PyInstaller --noconsole on Windows both stderr and stdout are
    ``None`` — writing to them raises ``TypeError: Cannot log to objects of
    type 'NoneType'``.
    """
    return getattr(sys, "stderr", None) is not None


def setup_logging(level: str = "INFO", log_file: str | Path | None = None) -> Path:
    """Configure loguru sinks. Always succeeds; never raises.

    Returns the resolved log file path.
    """
    logger.remove()

    if _has_console_stream():
        with contextlib.suppress(Exception):
            logger.add(sys.stderr, level=level, colorize=True)

    logfile = _resolve_log_file(log_file)
    try:
        logger.add(
            logfile,
            level="DEBUG",
            rotation="00:00",
            retention="7 days",
            serialize=True,
            enqueue=True,
        )
    except Exception as exc:
        # If the structured sink fails (permissions, disk full, etc.), at
        # least try a plain text fallback so we don't lose everything.
        with contextlib.suppress(Exception):
            fallback = logfile.with_suffix(".plain.log")
            logger.add(fallback, level="DEBUG", enqueue=True)
        # surface why the primary sink failed via the still-active sinks
        with contextlib.suppress(Exception):
            logger.warning("structured log sink failed: {}", exc)

    return logfile


__all__ = ["logger", "setup_logging"]
