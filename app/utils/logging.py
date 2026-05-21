"""Structured JSON logging via loguru."""

from __future__ import annotations

import sys
from datetime import datetime

from loguru import logger

from app.utils.paths import logs_dir


def setup_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(sys.stderr, level=level, colorize=True)
    logfile = logs_dir() / f"app-{datetime.now():%Y-%m-%d}.log"
    logger.add(
        logfile,
        level="DEBUG",
        rotation="00:00",
        retention="7 days",
        serialize=True,
        enqueue=True,
    )


__all__ = ["logger", "setup_logging"]
