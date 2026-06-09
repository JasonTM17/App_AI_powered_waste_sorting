"""Route-level builders for the expanded User app shell."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.agent.schemas import UserDeviceResponse, UserExperienceResponse
from app.agent.user_dashboard import build_user_analytics, build_user_history
from app.agent.user_experience_cards import build_user_experience_response
from app.agent.user_report_export import build_user_history_export_csv, build_user_report

if TYPE_CHECKING:
    from app.agent.runtime import AgentRuntime


def build_user_device(
    runtime: AgentRuntime,
    *,
    owner_account_id: int | None = None,
    owner_username: str | None = None,
) -> UserDeviceResponse:
    analytics = build_user_analytics(
        runtime,
        7,
        owner_account_id=owner_account_id,
        owner_username=owner_username,
    )
    recent = build_user_history(
        runtime,
        owner_account_id=owner_account_id,
        owner_username=owner_username,
        limit=8,
    )
    return UserDeviceResponse(
        generated_at=datetime.now().isoformat(),
        device_status=analytics.device_status,
        bins=analytics.bins,
        recent_activity=recent.rows,
        owner_username=owner_username or analytics.device_status.owner_username,
    )


def build_user_experience(
    runtime: AgentRuntime,
    range_days: int,
    *,
    owner_account_id: int | None = None,
    owner_username: str | None = None,
) -> UserExperienceResponse:
    analytics = build_user_analytics(
        runtime,
        range_days,
        owner_account_id=owner_account_id,
        owner_username=owner_username,
    )
    return build_user_experience_response(analytics, datetime.now().isoformat())


__all__ = [
    "build_user_device",
    "build_user_experience",
    "build_user_history_export_csv",
    "build_user_report",
]
