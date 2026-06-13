from datetime import datetime

import pytest

from app.agent.auth_crypto import (
    DEFAULT_SESSION_HOURS,
    PBKDF2_ITERATIONS,
    env_flag,
    hash_password,
    iso,
    session_hours,
    token_hash,
    utc_now,
    verify_password,
)


def test_hash_password():
    salt, p_hash = hash_password("secret_pass")
    assert isinstance(salt, str)
    assert isinstance(p_hash, str)
    assert len(salt) > 0
    assert len(p_hash) > 0


def test_verify_password():
    salt, p_hash = hash_password("my_secure_password")
    assert verify_password("my_secure_password", salt, p_hash, PBKDF2_ITERATIONS)
    assert not verify_password("wrong_password", salt, p_hash, PBKDF2_ITERATIONS)


def test_token_hash():
    t_hash = token_hash("my_token")
    assert isinstance(t_hash, str)
    assert len(t_hash) == 64  # sha256 hex


def test_utc_now():
    now = utc_now()
    assert isinstance(now, datetime)
    assert now.tzinfo is not None
    assert now.microsecond == 0


def test_iso():
    now = utc_now()
    iso_str = iso(now)
    assert isinstance(iso_str, str)
    assert "T" in iso_str


@pytest.mark.parametrize(
    "val, expected",
    [
        ("1", True),
        ("true", True),
        ("yes", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("", False),
    ],
)
def test_env_flag(monkeypatch, val, expected):
    monkeypatch.setenv("TEST_ENV_FLAG", val)
    assert env_flag("TEST_ENV_FLAG") == expected


def test_session_hours_default(monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_SESSION_HOURS", raising=False)
    assert session_hours() == DEFAULT_SESSION_HOURS


def test_session_hours_custom(monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_SESSION_HOURS", "24")
    assert session_hours() == 24


def test_session_hours_invalid(monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_SESSION_HOURS", "invalid")
    assert session_hours() == DEFAULT_SESSION_HOURS


def test_session_hours_limits(monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_SESSION_HOURS", "0")
    assert session_hours() == 1  # max(1, ...)
    monkeypatch.setenv("TRASH_SORTER_SESSION_HOURS", "200")
    assert session_hours() == 168  # min(168, ...)
