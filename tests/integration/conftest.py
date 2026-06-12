"""Integration test fixtures.

Clears every ``TRASH_SORTER_*`` / database / LLM-provider env var on each
test so the local agent boots from a deterministic slate (no leaked
session, no surprise default account, no live Supabase URL). This used
to be copy-pasted into four test files; keep it here so the canonical
list lives in one place.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

_AGENT_AUTH_ENV_VARS: tuple[str, ...] = (
    "TRASH_SORTER_AGENT_TOKEN",
    "TRASH_SORTER_ADMIN_TOKEN",
    "TRASH_SORTER_USER_TOKEN",
    "TRASH_SORTER_AUTH_DB",
    "TRASH_SORTER_AUTH_DATABASE_URL",
    "DATABASE_URL",
    "TRASH_SORTER_AUTH_DEV_DEFAULTS",
    "TRASH_SORTER_BOOTSTRAP_ADMIN_USERNAME",
    "TRASH_SORTER_BOOTSTRAP_ADMIN_PASSWORD",
    "TRASH_SORTER_SESSION_HOURS",
    "TRASH_SORTER_ALLOWED_ORIGINS",
    "OPENAI_API_KEY",
    "OPENAI_USER_ADVISOR_MODEL",
    "DEEPSEEK_API_KEY",
)


@pytest.fixture(autouse=True)
def _clear_agent_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset every auth/runtime env var to a clean baseline."""
    for name in _AGENT_AUTH_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
