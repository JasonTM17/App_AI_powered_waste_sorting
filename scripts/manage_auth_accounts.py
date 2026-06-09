"""Manage local web auth accounts."""

from __future__ import annotations

import argparse
from getpass import getpass

from app.agent.auth_password_policy import PasswordPolicyError
from app.agent.auth_service import AuthService


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Trash Sorter web login accounts")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create an account")
    create.add_argument("username")
    create.add_argument("--role", choices=["admin", "user"], required=True)
    create.add_argument("--force-change", action="store_true", help="Require password change at next login")

    password = sub.add_parser("set-password", help="Set an account password")
    password.add_argument("username")
    password.add_argument("--force-change", action="store_true", help="Require password change at next login")

    active = sub.add_parser("set-active", help="Enable or disable an account")
    active.add_argument("username")
    active.add_argument("--active", choices=["true", "false"], required=True)

    sub.add_parser("list", help="List accounts without sensitive fields")
    args = parser.parse_args()

    service = AuthService()
    try:
        if args.command == "create":
            service.create_account(
                args.username,
                _read_password(),
                args.role,
                password_default=args.force_change,
            )
            print(f"created {args.role} account: {args.username}")
        elif args.command == "set-password":
            if not service.set_password(
                args.username,
                _read_password(),
                temporary=args.force_change,
                revoke_sessions=True,
            ):
                raise SystemExit(f"account not found: {args.username}")
            print(f"updated password for: {args.username}")
    except PasswordPolicyError as exc:
        raise SystemExit(str(exc)) from exc
    if args.command == "set-active":
        enabled = args.active == "true"
        if not service.set_active(args.username, enabled):
            raise SystemExit(f"account not found: {args.username}")
        state = "enabled" if enabled else "disabled"
        print(f"{state} account: {args.username}")
    elif args.command == "list":
        for row in service.list_accounts():
            active_text = "active" if int(row["is_active"]) else "disabled"
            default_text = " default-password" if int(row["password_default"]) else ""
            print(f"{row['username']}\t{row['role']}\t{active_text}{default_text}")
    return 0


def _read_password() -> str:
    password = getpass("Password: ")
    confirm = getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("passwords do not match")
    if len(password) < 8:
        raise SystemExit("password must be at least 8 characters")
    return password


if __name__ == "__main__":
    raise SystemExit(main())
