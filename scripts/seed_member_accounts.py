"""Seed local EcoSort member accounts for the demo/user dashboard."""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.auth_password_policy import PasswordPolicyError
from app.agent.auth_service import AuthService
from app.utils.local_web import apply_local_auth_environment

MEMBERS: tuple[tuple[str, str], ...] = (
    ("nguyen-son", "Nguyễn Sơn"),
    ("ngoc-quyen", "Ngọc Quyên"),
    ("gia-kiet", "Gia Kiệt"),
    ("minh-huy", "Minh Huy"),
    ("hong-thuy", "Hồng Thủy"),
)
LEGACY_MEMBER_USERNAMES = tuple(display_name for _username, display_name in MEMBERS)


def main() -> int:
    apply_local_auth_environment(allow_dev_defaults=True)
    service = AuthService()
    existing = {str(row["username"]): row for row in service.list_accounts()}
    created: list[str] = []
    updated: list[str] = []
    disabled_legacy: list[str] = []

    credentials: list[tuple[str, str, str]] = []
    for username, display_name in MEMBERS:
        password = _temporary_password()
        credentials.append((username, display_name, password))
        if username in existing:
            service.set_password(username, password, revoke_sessions=True)
            service.set_display_name(username, display_name)
            service.set_active(username, True)
            updated.append(username)
        else:
            service.create_account(
                username,
                password,
                "user",
                display_name=display_name,
                password_default=False,
            )
            created.append(username)

    for username in LEGACY_MEMBER_USERNAMES:
        if username in existing and service.set_active(username, False):
            disabled_legacy.append(username)

    if created:
        print("created: " + ", ".join(created))
    if updated:
        print("updated: " + ", ".join(updated))
    if disabled_legacy:
        print("disabled legacy usernames: " + ", ".join(disabled_legacy))
    print("member credentials generated for this run:")
    for username, display_name, password in credentials:
        print(f"{display_name}\t{username}\t{password}")
    print("Store these passwords in the team password manager, then rotate if shared.")
    return 0


def _temporary_password() -> str:
    return f"EcoSort-{secrets.token_urlsafe(12)}-2026!"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PasswordPolicyError as exc:
        raise SystemExit(str(exc)) from exc
