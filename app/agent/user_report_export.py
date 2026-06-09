"""Scoped report and CSV export builders for User routes."""

from __future__ import annotations

import csv
import io
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING

from app.agent.schemas import UserHistoryItemDTO, UserReportCardDTO, UserReportResponse
from app.agent.user_dashboard import ALLOWED_ANALYTICS_RANGES, build_user_analytics
from app.core.history import HistoryService
from app.core.waste_categories import (
    ORGANIC,
    RECYCLABLE,
    WasteCategory,
    category_for_bin_index,
    category_for_class,
    category_for_command,
)

if TYPE_CHECKING:
    from app.agent.runtime import AgentRuntime


SAFE_USER_HISTORY_CSV_FIELDS = [
    "id",
    "ts",
    "cls_name",
    "confidence",
    "category",
    "route_label",
    "bin_index",
    "ack_status",
    "device_id",
]


def build_user_report(
    runtime: AgentRuntime,
    range_days: int,
    *,
    owner_account_id: int | None = None,
    owner_username: str | None = None,
) -> UserReportResponse:
    analytics = build_user_analytics(
        runtime,
        range_days,
        owner_account_id=owner_account_id,
        owner_username=owner_username,
    )
    return UserReportResponse(
        generated_at=datetime.now().isoformat(),
        range_days=analytics.range_days,
        analytics=analytics,
        summary_cards=_report_cards(analytics),
        export_url=f"/api/user/history/export.csv?range_days={analytics.range_days}",
        csv_safe_fields=SAFE_USER_HISTORY_CSV_FIELDS,
    )


def build_user_history_export_csv(
    runtime: AgentRuntime,
    range_days: int,
    *,
    owner_account_id: int | None = None,
    owner_username: str | None = None,
) -> str:
    rows = _history_since_range(
        runtime,
        _clean_range_days(range_days),
        owner_account_id=owner_account_id,
        owner_username=owner_username,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(SAFE_USER_HISTORY_CSV_FIELDS)
    for row in rows:
        item = safe_history_item(row)
        writer.writerow(
            [
                item.id,
                item.ts,
                item.cls_name,
                item.confidence,
                item.category,
                item.route_label or "",
                item.bin_index or "",
                item.ack_status or "",
                item.device_id or "",
            ]
        )
    return buffer.getvalue()


def safe_history_item(row) -> UserHistoryItemDTO:
    category = _row_category(row)
    return UserHistoryItemDTO(
        id=int(getattr(row, "id", 0) or 0),
        ts=str(getattr(row, "ts", "") or ""),
        cls_name=str(getattr(row, "cls_name", "") or ""),
        confidence=round(float(getattr(row, "conf", 0.0) or 0.0), 3),
        route_label=getattr(row, "route_label", None),
        bin_index=getattr(row, "bin_index", None),
        category=_category_slug(category),
        ack_status=getattr(row, "ack_status", None),
        device_id=getattr(row, "device_id", None),
        image_available=bool(getattr(row, "image_path", None) or getattr(row, "annotated_path", None)),
    )


def _history_since_range(
    runtime: AgentRuntime,
    range_days: int,
    *,
    owner_account_id: int | None,
    owner_username: str | None,
):
    start = datetime.combine(datetime.now().date() - timedelta(days=range_days - 1), time.min)
    service = HistoryService(runtime.history_file)
    try:
        return service.query(
            limit=1_000_000,
            since=start,
            owner_account_id=owner_account_id,
            owner_username=owner_username,
        )
    finally:
        service.close()


def _report_cards(analytics) -> list[UserReportCardDTO]:
    recycle_rate = round(analytics.eco_score.recyclable_rate)
    delta = analytics.comparison.delta
    delta_text = f"+{delta}" if delta > 0 else str(delta)
    return [
        UserReportCardDTO(
            title="Tong luot phan loai",
            value=str(analytics.total),
            detail=f"{analytics.range_days} ngay gan day",
        ),
        UserReportCardDTO(
            title="Eco Score",
            value=str(analytics.eco_score.score),
            detail=analytics.eco_score.label or "Dang theo doi",
            tone="success" if analytics.eco_score.score >= 70 else "warning",
        ),
        UserReportCardDTO(
            title="Ti le tai che",
            value=f"{recycle_rate}%",
            detail="Tinh tu cac luot da nhan dien",
            tone="success" if recycle_rate >= 40 else "neutral",
        ),
        UserReportCardDTO(
            title="So voi ky truoc",
            value=delta_text,
            detail=f"{analytics.comparison.delta_percent:.1f}% thay doi",
            tone="warning" if delta > 0 else "success",
        ),
    ]


def _row_category(row) -> WasteCategory:
    return (
        category_for_command(str(getattr(row, "uart_command", "") or ""))
        or category_for_bin_index(getattr(row, "bin_index", None))
        or category_for_class(str(getattr(row, "cls_name", "") or ""))
    )


def _category_slug(category: WasteCategory) -> str:
    if category.code == ORGANIC.code:
        return "organic"
    if category.code == RECYCLABLE.code:
        return "recyclable"
    return "inorganic"


def _clean_range_days(value: int) -> int:
    return value if value in ALLOWED_ANALYTICS_RANGES else 30


__all__ = [
    "SAFE_USER_HISTORY_CSV_FIELDS",
    "build_user_history_export_csv",
    "build_user_report",
    "safe_history_item",
]
