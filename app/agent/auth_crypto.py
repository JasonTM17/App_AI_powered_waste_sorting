"""Password/session crypto helpers for local account auth."""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
from datetime import UTC, datetime

SESSION_HOURS_ENV = "TRASH_SORTER_SESSION_HOURS"
DEFAULT_SESSION_HOURS = 12
PBKDF2_ITERATIONS = 210_000


def hash_password(password: str) -> tuple[str, str]:
    salt_bytes = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt_bytes, PBKDF2_ITERATIONS
    )
    return b64(salt_bytes), b64(digest)


def verify_password(password: str, salt: str, expected_hash: str, iterations: int) -> bool:
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), base64.b64decode(salt), iterations
    )
    return secrets.compare_digest(b64(digest), expected_hash)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso(value: datetime) -> str:
    return value.isoformat()


def env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def session_hours() -> int:
    try:
        return max(1, min(168, int(os.getenv(SESSION_HOURS_ENV, str(DEFAULT_SESSION_HOURS)))))
    except ValueError:
        return DEFAULT_SESSION_HOURS


__all__ = [
    "DEFAULT_SESSION_HOURS",
    "PBKDF2_ITERATIONS",
    "SESSION_HOURS_ENV",
    "env_flag",
    "hash_password",
    "iso",
    "session_hours",
    "token_hash",
    "utc_now",
    "verify_password",
]
