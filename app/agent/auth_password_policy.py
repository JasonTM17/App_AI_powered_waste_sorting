"""Password policy shared by auth API and local account CLI."""

from __future__ import annotations

WEAK_DEFAULT_PASSWORDS = {"admin123", "user123"}


class PasswordPolicyError(ValueError):
    pass


def validate_password_policy(
    username: str,
    password: str,
    *,
    allow_dev_default: bool = False,
) -> None:
    clean_username = username.strip().lower()
    if allow_dev_default and password in WEAK_DEFAULT_PASSWORDS:
        return
    if len(password) < 8:
        raise PasswordPolicyError("password must be at least 8 characters")
    if clean_username and password.lower() == clean_username:
        raise PasswordPolicyError("password must not match the username")
    if not allow_dev_default and password in WEAK_DEFAULT_PASSWORDS:
        raise PasswordPolicyError("password is reserved for local dev defaults")


__all__ = ["PasswordPolicyError", "validate_password_policy"]
