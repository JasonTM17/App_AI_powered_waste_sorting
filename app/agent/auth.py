"""Role-aware bearer-token auth for the local web agent."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Header, HTTPException, Query, status

from app.agent.auth_service import AuthService, account_auth_is_configured

TOKEN_ENV = "TRASH_SORTER_AGENT_TOKEN"
ADMIN_TOKEN_ENV = "TRASH_SORTER_ADMIN_TOKEN"
USER_TOKEN_ENV = "TRASH_SORTER_USER_TOKEN"

AgentRole = Literal["admin", "user"]

ADMIN_CAPABILITIES = [
    "camera",
    "live",
    "dataset",
    "history",
    "mapping",
    "settings",
    "logs",
    "training",
    "user_dashboard",
    "admin.users.manage",
    "admin.roles.manage",
    "admin.devices.manage",
    "admin.bin_map.manage",
    "admin.history.read_all",
    "admin.alerts.read_all",
    "admin.model.configure",
    "admin.audio.configure",
    "admin.reports.read_all",
    "admin.collection_schedules.manage",
    "admin.device_issues.manage",
]
USER_CAPABILITIES = [
    "user_dashboard",
    "user.bin_map.read",
    "user.alerts.read",
    "user.collection_schedule.read",
    "user.collection.mark_collected",
    "user.device_issues.create",
    "user.history.read_own",
    "user.account.manage_own",
]


@dataclass(frozen=True)
class AuthContext:
    role: AgentRole
    auth_required: bool
    account_id: int | None = None
    token_source: str = "dev"
    username: str | None = None
    session_expires_at: str | None = None
    password_default: bool = False

    @property
    def capabilities(self) -> list[str]:
        if self.role == "admin":
            return list(ADMIN_CAPABILITIES)
        return list(USER_CAPABILITIES)


def configured_token() -> str:
    return os.environ.get(TOKEN_ENV, "").strip()


def configured_admin_token() -> str:
    return os.environ.get(ADMIN_TOKEN_ENV, "").strip()


def configured_user_token() -> str:
    return os.environ.get(USER_TOKEN_ENV, "").strip()


def auth_is_configured() -> bool:
    return bool(
        configured_admin_token()
        or configured_user_token()
        or configured_token()
        or account_auth_is_configured()
    )


def authenticate_agent(
    authorization: Annotated[str | None, Header()] = None,
    query_token: Annotated[str | None, Query(alias="token")] = None,
) -> AuthContext:
    return authenticate_token_values(authorization=authorization, query_token=query_token)


def authenticate_token_values(
    *,
    authorization: str | None = None,
    query_token: str | None = None,
) -> AuthContext:
    token = _extract_token(authorization, query_token)
    if token:
        session = AuthService().authenticate_session(token)
        if session is not None:
            return AuthContext(
                role=session.role,
                auth_required=True,
                account_id=session.account_id,
                token_source="session",
                username=session.username,
                session_expires_at=session.expires_at,
                password_default=session.password_default,
            )
        match = _match_configured_token(token)
        if match is not None:
            return match

    if not auth_is_configured():
        return AuthContext(role="admin", auth_required=False, token_source="dev")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing agent token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_user_token(
    authorization: Annotated[str | None, Header()] = None,
    query_token: Annotated[str | None, Query(alias="token")] = None,
) -> AuthContext:
    return authenticate_token_values(authorization=authorization, query_token=query_token)


def require_admin_token(
    authorization: Annotated[str | None, Header()] = None,
    query_token: Annotated[str | None, Query(alias="token")] = None,
) -> AuthContext:
    context = authenticate_token_values(authorization=authorization, query_token=query_token)
    if context.role == "admin":
        return context
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


def require_password_changed(context: AuthContext) -> AuthContext:
    if context.password_default and context.token_source == "session":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password change required")
    return context


def require_active_user_token(
    authorization: Annotated[str | None, Header()] = None,
    query_token: Annotated[str | None, Query(alias="token")] = None,
) -> AuthContext:
    return require_password_changed(
        authenticate_token_values(authorization=authorization, query_token=query_token)
    )


def require_active_admin_token(
    authorization: Annotated[str | None, Header()] = None,
    query_token: Annotated[str | None, Query(alias="token")] = None,
) -> AuthContext:
    context = require_admin_token(authorization=authorization, query_token=query_token)
    return require_password_changed(context)


def require_agent_token(
    authorization: Annotated[str | None, Header()] = None,
    query_token: Annotated[str | None, Query(alias="token")] = None,
) -> AuthContext:
    return require_admin_token(authorization=authorization, query_token=query_token)


def _extract_token(authorization: str | None, query_token: str | None) -> str:
    if authorization:
        value = authorization.strip()
        if value.lower().startswith("bearer "):
            return value[7:].strip()
    return (query_token or "").strip()


def extract_token(authorization: str | None = None, query_token: str | None = None) -> str:
    return _extract_token(authorization, query_token)


def _match_configured_token(token: str) -> AuthContext | None:
    admin_token = configured_admin_token()
    user_token = configured_user_token()
    legacy_token = configured_token()
    if admin_token and secrets.compare_digest(token, admin_token):
        return AuthContext(role="admin", auth_required=True, token_source="env")
    if legacy_token and secrets.compare_digest(token, legacy_token):
        return AuthContext(role="admin", auth_required=True, token_source="env")
    if user_token and secrets.compare_digest(token, user_token):
        return AuthContext(role="user", auth_required=True, token_source="env")
    return None


__all__ = [
    "ADMIN_TOKEN_ENV",
    "TOKEN_ENV",
    "USER_TOKEN_ENV",
    "AgentRole",
    "AuthContext",
    "auth_is_configured",
    "authenticate_agent",
    "authenticate_token_values",
    "configured_admin_token",
    "configured_token",
    "configured_user_token",
    "extract_token",
    "require_active_admin_token",
    "require_active_user_token",
    "require_admin_token",
    "require_agent_token",
    "require_user_token",
]
