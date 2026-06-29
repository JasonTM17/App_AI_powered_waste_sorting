"""Transaction retry and heartbeat helpers for the Supabase hardware bridge."""

from __future__ import annotations

import json
import logging
import os
import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

import psycopg

LOGGER = logging.getLogger("supabase-hardware-bridge")
RETRYABLE_SQLSTATES = frozenset({"40001", "40P01", "55P03"})
T = TypeVar("T")


def run_transaction_domain(
    conn: psycopg.Connection[Any],
    name: str,
    operation: Callable[[], T],
    *,
    lock_timeout_ms: int,
    statement_timeout_ms: int,
    max_retries: int = 3,
    reset_caches: Callable[[], None] | None = None,
) -> T:
    """Run and commit one domain, retrying only transient PostgreSQL conflicts."""

    for attempt in range(max_retries + 1):
        try:
            conn.execute("select set_config('lock_timeout', %s, true)", (f"{lock_timeout_ms}ms",))
            conn.execute(
                "select set_config('statement_timeout', %s, true)",
                (f"{statement_timeout_ms}ms",),
            )
            result = operation()
            conn.commit()
            return result
        except psycopg.Error as exc:
            conn.rollback()
            if reset_caches is not None:
                reset_caches()
            sqlstate = str(getattr(exc, "sqlstate", "") or "")
            if sqlstate not in RETRYABLE_SQLSTATES or attempt >= max_retries:
                raise
            delay = min(1.0, 0.25 * (2**attempt)) * random.uniform(0.8, 1.2)
            LOGGER.warning(
                "Supabase %s transaction conflicted (SQLSTATE %s); retry %d/%d in %.2fs.",
                name,
                sqlstate,
                attempt + 1,
                max_retries,
                delay,
            )
            time.sleep(delay)
    raise RuntimeError(f"Unreachable retry state for {name}")


def write_heartbeat(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": time.time(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)


def heartbeat_is_fresh(path: Path, max_age_seconds: float) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        timestamp = float(payload["timestamp"])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return False
    age = time.time() - timestamp
    return -5.0 <= age <= max(1.0, max_age_seconds)


def env_positive_int(name: str, default: int, *, maximum: int = 300_000) -> int:
    try:
        value = int(str(os.getenv(name, default)).strip())
    except ValueError:
        return default
    return max(1, min(value, maximum))
