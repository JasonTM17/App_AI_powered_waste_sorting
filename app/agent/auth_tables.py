"""SQLAlchemy table declarations for local account auth."""

from __future__ import annotations

from sqlalchemy import Column, Integer, MetaData, String, Table, UniqueConstraint

metadata = MetaData()

accounts = Table(
    "accounts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String, nullable=False, unique=True),
    Column("role", String, nullable=False),
    Column("password_hash", String, nullable=False),
    Column("salt", String, nullable=False),
    Column("iterations", Integer, nullable=False),
    Column("is_active", Integer, nullable=False, default=1),
    Column("password_default", Integer, nullable=False, default=0),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
    Column("last_login_at", String),
)

sessions = Table(
    "sessions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", Integer, nullable=False),
    Column("token_hash", String, nullable=False, unique=True),
    Column("created_at", String, nullable=False),
    Column("expires_at", String, nullable=False),
    Column("revoked_at", String),
    Column("client_label", String, nullable=False, default=""),
)

chat_usage = Table(
    "chat_usage",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", Integer, nullable=False),
    Column("period", String, nullable=False),
    Column("used", Integer, nullable=False, default=0),
    Column("updated_at", String, nullable=False),
    UniqueConstraint("account_id", "period", name="uq_chat_usage_account_period"),
)

__all__ = ["accounts", "chat_usage", "metadata", "sessions"]
