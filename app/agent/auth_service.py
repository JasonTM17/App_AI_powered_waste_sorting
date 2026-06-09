"""Account and session auth for the local web agent."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import Engine

from app.agent.auth_crypto import (
    PBKDF2_ITERATIONS,
    SESSION_HOURS_ENV,
    env_flag,
    hash_password,
    iso,
    session_hours,
    token_hash,
    utc_now,
    verify_password,
)
from app.agent.auth_password_policy import validate_password_policy
from app.agent.auth_tables import accounts, chat_usage, metadata, sessions
from app.utils.paths import auth_db_path

AUTH_DB_ENV = "TRASH_SORTER_AUTH_DB"
AUTH_DATABASE_URL_ENV = "TRASH_SORTER_AUTH_DATABASE_URL"
DATABASE_URL_ENV = "DATABASE_URL"
DEV_DEFAULTS_ENV = "TRASH_SORTER_AUTH_DEV_DEFAULTS"
BOOTSTRAP_ADMIN_USERNAME_ENV = "TRASH_SORTER_BOOTSTRAP_ADMIN_USERNAME"
BOOTSTRAP_ADMIN_PASSWORD_ENV = "TRASH_SORTER_BOOTSTRAP_ADMIN_PASSWORD"
USER_CHAT_MONTHLY_LIMIT = 36
AuthRole = Literal["admin", "user"]


@dataclass(frozen=True)
class AuthIdentity:
    account_id: int
    role: AuthRole
    username: str
    expires_at: str
    password_default: bool = False


@dataclass(frozen=True)
class LoginResult:
    token: str
    identity: AuthIdentity


@dataclass(frozen=True)
class ChatQuota:
    limit: int
    used: int
    remaining: int
    reset_at: str
    exceeded: bool = False

    def as_response_fields(self) -> dict[str, object]:
        return {
            "quota_limit": self.limit,
            "quota_used": self.used,
            "quota_remaining": self.remaining,
            "quota_reset_at": self.reset_at,
            "quota_exceeded": self.exceeded,
        }


class InactiveAccountError(Exception):
    pass


class AuthService:
    def __init__(self, db_path: Path | None = None, database_url: str | None = None):
        self.database_url = database_url or (configured_auth_database_url() if db_path is None else "")
        self.db_path = db_path or configured_auth_db_path()
        if self.database_url:
            self._engine: Engine = create_engine(self.database_url, future=True, pool_pre_ping=True)
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        metadata.create_all(self._engine)
        self._ensure_columns()
        self.seed_configured_accounts()

    def has_accounts(self) -> bool:
        with self._engine.begin() as conn:
            return bool(conn.execute(select(accounts.c.id).limit(1)).first())

    def login(self, username: str, password: str, client_label: str = "") -> LoginResult | None:
        clean_username = username.strip()
        if not clean_username or not password:
            return None
        with self._engine.begin() as conn:
            row = conn.execute(
                select(accounts).where(accounts.c.username == clean_username)
            ).mappings().first()
            if row is None or not verify_password(
                password,
                str(row["salt"]),
                str(row["password_hash"]),
                int(row["iterations"]),
            ):
                return None
            if not int(row["is_active"]):
                raise InactiveAccountError(clean_username)
            now = utc_now()
            expires_at = now + timedelta(hours=session_hours())
            token = secrets.token_urlsafe(32)
            conn.execute(
                sessions.insert().values(
                    account_id=int(row["id"]),
                    token_hash=token_hash(token),
                    created_at=iso(now),
                    expires_at=iso(expires_at),
                    revoked_at=None,
                    client_label=client_label.strip()[:120],
                )
            )
            conn.execute(
                accounts.update()
                .where(accounts.c.id == int(row["id"]))
                .values(last_login_at=iso(now), updated_at=iso(now))
            )
        identity = AuthIdentity(
            account_id=int(row["id"]),
            role=_role(row["role"]),
            username=clean_username,
            expires_at=iso(expires_at),
            password_default=bool(int(row["password_default"])),
        )
        return LoginResult(token=token, identity=identity)

    def authenticate_session(self, token: str) -> AuthIdentity | None:
        if not token:
            return None
        now = iso(utc_now())
        stmt = (
            select(
                accounts.c.username,
                accounts.c.id,
                accounts.c.role,
                accounts.c.is_active,
                accounts.c.password_default,
                sessions.c.expires_at,
                sessions.c.revoked_at,
            )
            .select_from(sessions.join(accounts, sessions.c.account_id == accounts.c.id))
            .where(sessions.c.token_hash == token_hash(token))
        )
        with self._engine.begin() as conn:
            row = conn.execute(stmt).mappings().first()
        if row is None or row["revoked_at"] or str(row["expires_at"]) <= now:
            return None
        if not int(row["is_active"]):
            return None
        return AuthIdentity(
            account_id=int(row["id"]),
            role=_role(row["role"]),
            username=str(row["username"]),
            expires_at=str(row["expires_at"]),
            password_default=bool(int(row["password_default"])),
        )

    def revoke_session(self, token: str) -> bool:
        if not token:
            return False
        with self._engine.begin() as conn:
            result = conn.execute(
                sessions.update()
                .where(sessions.c.token_hash == token_hash(token))
                .where(sessions.c.revoked_at.is_(None))
                .values(revoked_at=iso(utc_now()))
            )
            return int(result.rowcount or 0) > 0

    def create_account(
        self,
        username: str,
        password: str,
        role: AuthRole,
        *,
        password_default: bool = False,
        allow_dev_default: bool = False,
    ) -> None:
        clean_username = username.strip()
        if not clean_username or not password:
            raise ValueError("username and password are required")
        validate_password_policy(
            clean_username,
            password,
            allow_dev_default=allow_dev_default,
        )
        salt, password_hash = hash_password(password)
        now = iso(utc_now())
        with self._engine.begin() as conn:
            conn.execute(
                accounts.insert().values(
                    username=clean_username,
                    role=role,
                    password_hash=password_hash,
                    salt=salt,
                    iterations=PBKDF2_ITERATIONS,
                    is_active=1,
                    password_default=1 if password_default else 0,
                    created_at=now,
                    updated_at=now,
                    last_login_at=None,
                )
            )

    def set_password(
        self,
        username: str,
        password: str,
        *,
        temporary: bool = False,
        revoke_sessions: bool = False,
    ) -> bool:
        clean_username = username.strip()
        validate_password_policy(clean_username, password)
        salt, password_hash = hash_password(password)
        with self._engine.begin() as conn:
            result = conn.execute(
                accounts.update()
                .where(accounts.c.username == clean_username)
                .values(
                    password_hash=password_hash,
                    salt=salt,
                    iterations=PBKDF2_ITERATIONS,
                    password_default=1 if temporary else 0,
                    updated_at=iso(utc_now()),
                )
            )
            changed = int(result.rowcount or 0) > 0
            if changed and revoke_sessions:
                account_id = conn.execute(
                    select(accounts.c.id).where(accounts.c.username == clean_username)
                ).scalar_one_or_none()
                if account_id is not None:
                    conn.execute(
                        sessions.update()
                        .where(sessions.c.account_id == int(account_id))
                        .where(sessions.c.revoked_at.is_(None))
                        .values(revoked_at=iso(utc_now()))
                    )
            return changed

    def change_password(
        self,
        *,
        account_id: int,
        current_password: str,
        new_password: str,
        current_token: str,
    ) -> bool:
        with self._engine.begin() as conn:
            row = conn.execute(select(accounts).where(accounts.c.id == account_id)).mappings().first()
            if row is None:
                return False
            if not verify_password(
                current_password,
                str(row["salt"]),
                str(row["password_hash"]),
                int(row["iterations"]),
            ):
                return False
            validate_password_policy(str(row["username"]), new_password)
            salt, password_hash = hash_password(new_password)
            now = iso(utc_now())
            conn.execute(
                accounts.update()
                .where(accounts.c.id == account_id)
                .values(
                    password_hash=password_hash,
                    salt=salt,
                    iterations=PBKDF2_ITERATIONS,
                    password_default=0,
                    updated_at=now,
                )
            )
            current_hash = token_hash(current_token)
            conn.execute(
                sessions.update()
                .where(sessions.c.account_id == account_id)
                .where(sessions.c.token_hash != current_hash)
                .where(sessions.c.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            return True

    def revoke_account_sessions(self, username: str, *, except_token: str = "") -> bool:
        clean_username = username.strip()
        now = iso(utc_now())
        with self._engine.begin() as conn:
            account_id = conn.execute(
                select(accounts.c.id).where(accounts.c.username == clean_username)
            ).scalar_one_or_none()
            if account_id is None:
                return False
            stmt = (
                sessions.update()
                .where(sessions.c.account_id == int(account_id))
                .where(sessions.c.revoked_at.is_(None))
            )
            if except_token:
                stmt = stmt.where(sessions.c.token_hash != token_hash(except_token))
            conn.execute(stmt.values(revoked_at=now))
            return True

    def set_active(self, username: str, active: bool) -> bool:
        with self._engine.begin() as conn:
            result = conn.execute(
                accounts.update()
                .where(accounts.c.username == username.strip())
                .values(is_active=1 if active else 0, updated_at=iso(utc_now()))
            )
            changed = int(result.rowcount or 0) > 0
            if changed and not active:
                account_id = conn.execute(
                    select(accounts.c.id).where(accounts.c.username == username.strip())
                ).scalar_one_or_none()
                if account_id is not None:
                    conn.execute(
                        sessions.update()
                        .where(sessions.c.account_id == int(account_id))
                        .where(sessions.c.revoked_at.is_(None))
                        .values(revoked_at=iso(utc_now()))
                    )
            return changed

    def list_accounts(self) -> list[dict[str, object]]:
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(
                    accounts.c.username,
                    accounts.c.id,
                    accounts.c.role,
                    accounts.c.is_active,
                    accounts.c.password_default,
                    accounts.c.created_at,
                    accounts.c.last_login_at,
                ).order_by(accounts.c.username)
            ).mappings().all()
        return [dict(row) for row in rows]

    def get_user_chat_quota(self, account_id: int, *, limit: int = USER_CHAT_MONTHLY_LIMIT) -> ChatQuota:
        period = _current_chat_period()
        with self._engine.begin() as conn:
            row = conn.execute(
                select(chat_usage.c.used).where(chat_usage.c.account_id == account_id).where(chat_usage.c.period == period)
            ).mappings().first()
        used = int(row["used"]) if row is not None else 0
        return _quota_from_used(used, limit=limit)

    def consume_user_chat_quota(self, account_id: int, *, limit: int = USER_CHAT_MONTHLY_LIMIT) -> ChatQuota:
        period = _current_chat_period()
        now = iso(utc_now())
        with self._engine.begin() as conn:
            row = conn.execute(
                select(chat_usage.c.id, chat_usage.c.used)
                .where(chat_usage.c.account_id == account_id)
                .where(chat_usage.c.period == period)
            ).mappings().first()
            used = int(row["used"]) if row is not None else 0
            if used >= limit:
                return _quota_from_used(used, limit=limit, exceeded=True)
            next_used = used + 1
            if row is None:
                conn.execute(
                    chat_usage.insert().values(
                        account_id=account_id,
                        period=period,
                        used=next_used,
                        updated_at=now,
                    )
                )
            else:
                conn.execute(
                    chat_usage.update()
                    .where(chat_usage.c.id == int(row["id"]))
                    .values(used=next_used, updated_at=now)
                )
        return _quota_from_used(next_used, limit=limit)

    def seed_configured_accounts(self) -> None:
        if env_flag(DEV_DEFAULTS_ENV):
            self._create_if_missing(
                "admin",
                "admin123",
                "admin",
                password_default=True,
                allow_dev_default=True,
            )
            self._create_if_missing(
                "user",
                "user123",
                "user",
                password_default=True,
                allow_dev_default=True,
            )
        username = os.getenv(BOOTSTRAP_ADMIN_USERNAME_ENV, "").strip()
        password = os.getenv(BOOTSTRAP_ADMIN_PASSWORD_ENV, "")
        if username and password:
            self._create_if_missing(username, password, "admin")

    def _create_if_missing(
        self,
        username: str,
        password: str,
        role: AuthRole,
        *,
        password_default: bool = False,
        allow_dev_default: bool = False,
    ) -> None:
        with self._engine.begin() as conn:
            exists = conn.execute(
                select(accounts.c.id).where(accounts.c.username == username)
            ).first()
        if exists is None:
            self.create_account(
                username,
                password,
                role,
                password_default=password_default,
                allow_dev_default=allow_dev_default,
            )

    def _ensure_columns(self) -> None:
        with self._engine.begin() as conn:
            cols = {str(row["name"]) for row in inspect(conn).get_columns("accounts")}
            if "password_default" not in cols:
                conn.execute(
                    text("ALTER TABLE accounts ADD COLUMN password_default INTEGER DEFAULT 0")
                )
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sessions_account ON sessions(account_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_chat_usage_account_period ON chat_usage(account_id, period)"))


def configured_auth_database_url() -> str:
    raw = (
        os.getenv(AUTH_DATABASE_URL_ENV, "").strip()
        or os.getenv(DATABASE_URL_ENV, "").strip()
    )
    return normalize_database_url(raw)


def configured_auth_db_path() -> Path:
    raw = os.getenv(AUTH_DB_ENV, "").strip()
    return Path(raw) if raw else auth_db_path()


def normalize_database_url(raw: str) -> str:
    value = raw.strip()
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value.removeprefix("postgres://")
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value.removeprefix("postgresql://")
    return value


def account_auth_is_configured() -> bool:
    service = AuthService()
    return service.has_accounts()


def _role(value: object) -> AuthRole:
    return "admin" if str(value) == "admin" else "user"


def _current_chat_period() -> str:
    return utc_now().strftime("%Y-%m")


def _quota_reset_at() -> str:
    now = utc_now()
    year = now.year + 1 if now.month == 12 else now.year
    month = 1 if now.month == 12 else now.month + 1
    return datetime(year, month, 1, tzinfo=timezone.utc).isoformat()


def _quota_from_used(used: int, *, limit: int, exceeded: bool = False) -> ChatQuota:
    clean_used = max(0, used)
    return ChatQuota(
        limit=limit,
        used=clean_used,
        remaining=max(0, limit - clean_used),
        reset_at=_quota_reset_at(),
        exceeded=exceeded or clean_used >= limit,
    )


__all__ = [
    "AUTH_DATABASE_URL_ENV",
    "AUTH_DB_ENV",
    "BOOTSTRAP_ADMIN_PASSWORD_ENV",
    "BOOTSTRAP_ADMIN_USERNAME_ENV",
    "DATABASE_URL_ENV",
    "DEV_DEFAULTS_ENV",
    "SESSION_HOURS_ENV",
    "USER_CHAT_MONTHLY_LIMIT",
    "AuthIdentity",
    "AuthService",
    "ChatQuota",
    "InactiveAccountError",
    "LoginResult",
    "account_auth_is_configured",
    "configured_auth_database_url",
    "configured_auth_db_path",
    "normalize_database_url",
]
