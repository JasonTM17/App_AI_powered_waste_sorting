"""User-safe dashboard aggregation for the local agent."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING

from app.agent.schemas import (
    UserDashboardResponse,
    WasteClassCountDTO,
    WellnessInsightDTO,
)
from app.core.history import HistoryService

if TYPE_CHECKING:
    from app.agent.runtime import AgentRuntime

RECENT_WASTE_LIMIT = 100
INSIGHT_MIN_COUNT = 3
INSIGHT_MIN_RATIO = 0.25

BOTTLE_CLASSES = frozenset(
    {
        "Plastic bottle",
        "Glass bottle",
        "Milk bottle",
    }
)

FAST_FOOD_CLASSES = frozenset(
    {
        "Disposable tableware",
        "Paper cups",
        "Plastic cup",
        "Postal packaging",
    }
)


def build_user_dashboard(runtime: AgentRuntime) -> UserDashboardResponse:
    rows = _recent_history(runtime)
    counts = Counter(str(getattr(row, "cls_name", "") or "") for row in rows)
    counts.pop("", None)
    sample_size = sum(counts.values())
    return UserDashboardResponse(
        generated_at=datetime.now().isoformat(),
        bins=runtime.bin_fullness(),
        recent_waste=_waste_counts(rows, counts),
        insights=_wellness_insights(counts, sample_size),
        sample_size=sample_size,
    )


def _recent_history(runtime: AgentRuntime):
    service = HistoryService(runtime.history_file)
    try:
        return service.query(limit=RECENT_WASTE_LIMIT)
    finally:
        service.close()


def _waste_counts(rows, counts: Counter[str]) -> list[WasteClassCountDTO]:
    route_by_class: dict[str, tuple[int | None, str | None]] = {}
    for row in rows:
        cls_name = str(getattr(row, "cls_name", "") or "")
        if cls_name and cls_name not in route_by_class:
            route_by_class[cls_name] = (
                getattr(row, "bin_index", None),
                getattr(row, "route_label", None),
            )
    return [
        WasteClassCountDTO(
            cls_name=cls_name,
            count=count,
            bin_index=route_by_class.get(cls_name, (None, None))[0],
            route_label=route_by_class.get(cls_name, (None, None))[1],
        )
        for cls_name, count in counts.most_common(8)
    ]


def _wellness_insights(counts: Counter[str], sample_size: int) -> list[WellnessInsightDTO]:
    insights: list[WellnessInsightDTO] = []
    bottle_count = sum(counts[name] for name in BOTTLE_CLASSES)
    fast_food_count = sum(counts[name] for name in FAST_FOOD_CLASSES)
    if _is_prominent(bottle_count, sample_size):
        insights.append(
            WellnessInsightDTO(
                kind="hydration",
                title="Nhieu chai nuoc",
                message=(
                    "Gan day co nhieu chai nuoc trong thung. Co the ban dang uong du nuoc; "
                    "neu tien, hay dung binh ca nhan va tai che chai dung cach."
                ),
                severity="info",
            )
        )
    if _is_prominent(fast_food_count, sample_size):
        insights.append(
            WellnessInsightDTO(
                kind="fast_food",
                title="Nhieu bao bi do an nhanh",
                message=(
                    "Gan day co nhieu ly, hop hoac bao bi do an nhanh. Nen giam bot khi co the "
                    "va uu tien bua an tu chuan bi de giu thoi quen tot hon."
                ),
                severity="warning",
            )
        )
    if not insights:
        insights.append(
            WellnessInsightDTO(
                kind="balance",
                title="Chua co mau noi bat",
                message="Du lieu gan day chua cho thay thoi quen nao noi troi.",
                severity="info",
            )
        )
    return insights


def _is_prominent(count: int, sample_size: int) -> bool:
    if sample_size <= 0:
        return False
    return count >= INSIGHT_MIN_COUNT and count / sample_size >= INSIGHT_MIN_RATIO


__all__ = ["build_user_dashboard"]
