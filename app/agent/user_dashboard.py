"""User-safe dashboard and analytics aggregation for the local agent."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from app.agent.ai_chat_service import (
    DEFAULT_DEEPSEEK_MODEL,
    DEFAULT_USER_PROFILE,
    build_chat_response,
    deepseek_available,
)
from app.agent.chat_knowledge_service import retrieve_knowledge_snippets
from app.agent.schemas import (
    DeviceStatusDTO,
    EcoScoreDTO,
    UserAdvisorResponse,
    UserAnalyticsResponse,
    UserDailyWasteDTO,
    UserDashboardResponse,
    UserHistoryItemDTO,
    UserHistoryResponse,
    UserMonthlyWasteDTO,
    UserPeriodComparisonDTO,
    UserRouteTotalDTO,
    UserYesterdaySummaryDTO,
    WasteClassCountDTO,
    WellnessInsightDTO,
)
from app.core.history import HistoryService
from app.core.waste_categories import (
    INORGANIC,
    ORGANIC,
    RECYCLABLE,
    WasteCategory,
    category_for_bin_index,
    category_for_class,
    category_for_command,
)

if TYPE_CHECKING:
    from app.agent.runtime import AgentRuntime

RECENT_WASTE_LIMIT = 100
INSIGHT_MIN_COUNT = 3
INSIGHT_MIN_RATIO = 0.25
ALLOWED_ANALYTICS_RANGES = (7, 30, 90, 180)
ANALYTICS_QUERY_LIMIT = 1_000_000

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


def build_user_dashboard(
    runtime: AgentRuntime,
    *,
    owner_account_id: int | None = None,
    owner_username: str | None = None,
) -> UserDashboardResponse:
    rows = _recent_history(runtime, owner_account_id=owner_account_id, owner_username=owner_username)
    counts = Counter(str(getattr(row, "cls_name", "") or "") for row in rows)
    counts.pop("", None)
    sample_size = sum(counts.values())
    return UserDashboardResponse(
        generated_at=datetime.now().isoformat(),
        bins=runtime.bin_fullness(),
        recent_waste=_waste_counts(rows, counts, sample_size, limit=8),
        insights=_wellness_insights(counts, sample_size),
        sample_size=sample_size,
    )


def build_user_analytics(
    runtime: AgentRuntime,
    range_days: int,
    *,
    owner_account_id: int | None = None,
    owner_username: str | None = None,
) -> UserAnalyticsResponse:
    range_days = _clean_range_days(range_days)
    today = datetime.now().date()
    start_date = today - timedelta(days=range_days - 1)
    previous_start = start_date - timedelta(days=range_days)
    rows = _history_since(
        runtime,
        datetime.combine(previous_start, time.min),
        owner_account_id=owner_account_id,
        owner_username=owner_username,
    )
    thirty_day_rows = _history_since(
        runtime,
        datetime.combine(today - timedelta(days=29), time.min),
        owner_account_id=owner_account_id,
        owner_username=owner_username,
    )
    current_rows = _rows_between(rows, start_date, today)
    previous_rows = _rows_between(rows, previous_start, start_date - timedelta(days=1))
    today_rows = _rows_between(rows, today, today)
    seven_day_rows = _rows_between(rows, today - timedelta(days=6), today)
    yesterday_date = today - timedelta(days=1)
    yesterday_rows = _rows_between(rows, yesterday_date, yesterday_date)
    counts = Counter(str(getattr(row, "cls_name", "") or "") for row in current_rows)
    counts.pop("", None)
    total = sum(counts.values())
    previous_total = len(previous_rows)
    route_totals = _route_totals(current_rows)
    average_confidence = _average_confidence(current_rows)
    eco_score = _eco_score(route_totals, current_rows, range_days, average_confidence)
    device_status = _device_status(runtime, owner_username)
    insights = _analytics_insights(route_totals, total, previous_total)
    insights.extend(_wellness_insights(counts, total))
    insights = _dedupe_insights(insights)
    return UserAnalyticsResponse(
        generated_at=datetime.now().isoformat(),
        range_days=range_days,  # type: ignore[arg-type]
        total=total,
        today_total=len(today_rows),
        seven_day_total=len(seven_day_rows),
        thirty_day_total=len(thirty_day_rows),
        average_confidence=round(average_confidence, 1),
        eco_score=eco_score,
        device_status=device_status,
        advice=insights,
        recent_classifications=_history_items(current_rows[:12]),
        comparison=_period_comparison(total, previous_total),
        bins=runtime.bin_fullness(),
        route_totals=route_totals,
        top_classes=_waste_counts(current_rows, counts, total, limit=10),
        daily=_daily_series(current_rows, start_date, today),
        monthly=_monthly_series(current_rows, start_date, today) if range_days >= 30 else [],
        yesterday=UserYesterdaySummaryDTO(
            date=yesterday_date.isoformat(),
            total=len(yesterday_rows),
            top_classes=_waste_counts(
                yesterday_rows,
                Counter(str(getattr(row, "cls_name", "") or "") for row in yesterday_rows),
                len(yesterday_rows),
                limit=6,
            ),
            route_totals=_route_totals(yesterday_rows),
        ),
        insights=insights,
        advisor_available=deepseek_available(),
        advisor_model=_deepseek_model() if deepseek_available() else "",
    )


def build_user_advisor(
    runtime: AgentRuntime,
    *,
    range_days: int,
    question: str = "",
    owner_account_id: int | None = None,
    owner_username: str | None = None,
) -> UserAdvisorResponse:
    analytics = build_user_analytics(
        runtime,
        range_days,
        owner_account_id=owner_account_id,
        owner_username=owner_username,
    )
    fallback = _local_advisor_message(analytics)
    advisor_context = _advisor_payload(analytics)
    prompt = question.strip() or "Hãy tư vấn dựa trên dashboard của tôi."
    response = build_chat_response(
        role="user",
        message=prompt,
        context=advisor_context,
        profile=DEFAULT_USER_PROFILE,
        knowledge_snippets=retrieve_knowledge_snippets(
            role="user",
            question=prompt,
            context=advisor_context,
        ),
        conversation_style="Tư vấn sức khỏe/thói quen ở mức tổng quát, không chẩn đoán y tế.",
    )
    return UserAdvisorResponse(
        generated_at=datetime.now().isoformat(),
        available=response.available,
        provider=response.provider,
        model=response.model,
        profile=response.profile,
        range_days=analytics.range_days,
        message=response.message if response.available else f"{response.message} {fallback}",
        local_insights=analytics.insights,
        knowledge_used=response.knowledge_used,
        safety_notice=response.safety_notice,
    )


def build_user_history(
    runtime: AgentRuntime,
    *,
    owner_account_id: int | None = None,
    owner_username: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> UserHistoryResponse:
    service = HistoryService(runtime.history_file)
    try:
        rows = service.query(
            limit=max(1, min(limit, 100)),
            offset=max(0, offset),
            owner_account_id=owner_account_id,
            owner_username=owner_username,
        )
    finally:
        service.close()
    return UserHistoryResponse(rows=_history_items(rows), total=len(rows))


def _recent_history(
    runtime: AgentRuntime,
    *,
    owner_account_id: int | None = None,
    owner_username: str | None = None,
):
    service = HistoryService(runtime.history_file)
    try:
        return service.query(
            limit=RECENT_WASTE_LIMIT,
            owner_account_id=owner_account_id,
            owner_username=owner_username,
        )
    finally:
        service.close()


def _history_since(
    runtime: AgentRuntime,
    since: datetime,
    *,
    owner_account_id: int | None = None,
    owner_username: str | None = None,
):
    service = HistoryService(runtime.history_file)
    try:
        return service.query(
            limit=ANALYTICS_QUERY_LIMIT,
            since=since,
            owner_account_id=owner_account_id,
            owner_username=owner_username,
        )
    finally:
        service.close()


def _waste_counts(
    rows,
    counts: Counter[str],
    sample_size: int,
    *,
    limit: int,
) -> list[WasteClassCountDTO]:
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
            percent=_percent(count, sample_size),
        )
        for cls_name, count in counts.most_common(limit)
        if cls_name
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


def _clean_range_days(range_days: int) -> int:
    if range_days in ALLOWED_ANALYTICS_RANGES:
        return range_days
    return 30


def _rows_between(rows, start: date, end: date):
    return [row for row in rows if (row_date := _row_date(row)) is not None and start <= row_date <= end]


def _row_date(row) -> date | None:
    raw = str(getattr(row, "ts", "") or "")
    if len(raw) < 10:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _row_category(row) -> WasteCategory:
    return (
        category_for_command(str(getattr(row, "uart_command", "") or ""))
        or category_for_bin_index(getattr(row, "bin_index", None))
        or category_for_class(str(getattr(row, "cls_name", "") or ""))
    )


def _route_totals(rows) -> list[UserRouteTotalDTO]:
    counts: Counter[str] = Counter(_row_category(row).code for row in rows)
    total = sum(counts.values())
    return [
        UserRouteTotalDTO(
            command=category.code,  # type: ignore[arg-type]
            route_label=category.name,
            bin_index=category.bin_index,
            count=counts.get(category.code, 0),
            percent=_percent(counts.get(category.code, 0), total),
        )
        for category in (ORGANIC, INORGANIC, RECYCLABLE)
    ]


def _daily_series(rows, start: date, end: date) -> list[UserDailyWasteDTO]:
    grouped: dict[str, Counter[str]] = {}
    for row in rows:
        row_date = _row_date(row)
        if row_date is None:
            continue
        key = row_date.isoformat()
        grouped.setdefault(key, Counter())[_row_category(row).code] += 1
    out: list[UserDailyWasteDTO] = []
    current = start
    while current <= end:
        counts = grouped.get(current.isoformat(), Counter())
        out.append(_daily_dto(current.isoformat(), counts))
        current += timedelta(days=1)
    return out


def _monthly_series(rows, start: date, end: date) -> list[UserMonthlyWasteDTO]:
    grouped: dict[str, Counter[str]] = {}
    for row in rows:
        row_date = _row_date(row)
        if row_date is None:
            continue
        key = row_date.strftime("%Y-%m")
        grouped.setdefault(key, Counter())[_row_category(row).code] += 1
    out: list[UserMonthlyWasteDTO] = []
    current = date(start.year, start.month, 1)
    last = date(end.year, end.month, 1)
    while current <= last:
        key = current.strftime("%Y-%m")
        counts = grouped.get(key, Counter())
        out.append(
            UserMonthlyWasteDTO(
                month=key,
                total=sum(counts.values()),
                organic=counts.get(ORGANIC.code, 0),
                inorganic=counts.get(INORGANIC.code, 0),
                recyclable=counts.get(RECYCLABLE.code, 0),
            )
        )
        current = _next_month(current)
    return out


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _daily_dto(key: str, counts: Counter[str]) -> UserDailyWasteDTO:
    return UserDailyWasteDTO(
        date=key,
        total=sum(counts.values()),
        organic=counts.get(ORGANIC.code, 0),
        inorganic=counts.get(INORGANIC.code, 0),
        recyclable=counts.get(RECYCLABLE.code, 0),
    )


def _period_comparison(total: int, previous_total: int) -> UserPeriodComparisonDTO:
    delta = total - previous_total
    return UserPeriodComparisonDTO(
        previous_total=previous_total,
        delta=delta,
        delta_percent=_percent(delta, previous_total) if previous_total else 0.0,
    )


def _analytics_insights(
    route_totals: list[UserRouteTotalDTO],
    total: int,
    previous_total: int,
) -> list[WellnessInsightDTO]:
    if total <= 0:
        return [
            WellnessInsightDTO(
                kind="empty",
                title="Chua co du lieu",
                message="May chua ghi nhan rac trong khoang thoi gian nay.",
                severity="info",
            )
        ]
    by_command = {item.command: item for item in route_totals}
    insights: list[WellnessInsightDTO] = []
    recyclable_percent = by_command.get("I", UserRouteTotalDTO(command="I", route_label="", bin_index=3)).percent
    inorganic_percent = by_command.get("R", UserRouteTotalDTO(command="R", route_label="", bin_index=2)).percent
    if recyclable_percent >= 45:
        insights.append(
            WellnessInsightDTO(
                kind="recycling",
                title="Ti le tai che tot",
                message="Ti le rac tai che dang cao. Hay tiep tuc rua sach chai, lon va giay truoc khi bo.",
                severity="info",
            )
        )
    if inorganic_percent >= 55:
        insights.append(
            WellnessInsightDTO(
                kind="single_use",
                title="Nhieu rac vo co",
                message="Rac vo co dang chiem ty le cao. Co the giam do dung mot lan khi mua do an/uong.",
                severity="warning",
            )
        )
    if previous_total and total > previous_total * 1.25:
        insights.append(
            WellnessInsightDTO(
                kind="increase",
                title="Luong rac tang",
                message="Tong luong rac cao hon ky truoc. Nen xem lai cac ngay tang dot bien de dieu chinh thoi quen.",
                severity="warning",
            )
        )
    return insights


def _dedupe_insights(items: Iterable[WellnessInsightDTO]) -> list[WellnessInsightDTO]:
    out: list[WellnessInsightDTO] = []
    seen: set[str] = set()
    for item in items:
        key = item.kind
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out[:6]


def _percent(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((count / total) * 100, 1)


def _average_confidence(rows) -> float:
    values: list[float] = []
    for row in rows:
        try:
            values.append(float(getattr(row, "conf", 0.0) or 0.0) * 100)
        except (TypeError, ValueError):
            continue
    return round(sum(values) / len(values), 1) if values else 0.0


def _eco_score(
    route_totals: list[UserRouteTotalDTO],
    rows,
    range_days: int,
    average_confidence: float,
) -> EcoScoreDTO:
    by_command = {item.command: item for item in route_totals}
    organic_rate = by_command.get("O", UserRouteTotalDTO(command="O", route_label="", bin_index=1)).percent
    inorganic_rate = by_command.get("R", UserRouteTotalDTO(command="R", route_label="", bin_index=2)).percent
    recyclable_rate = by_command.get("I", UserRouteTotalDTO(command="I", route_label="", bin_index=3)).percent
    active_days = {_row_date(row) for row in rows if _row_date(row) is not None}
    consistency_score = round(min(100.0, (len(active_days) / max(1, range_days)) * 100), 1)
    raw_score = (
        35
        + recyclable_rate * 0.32
        + organic_rate * 0.14
        + consistency_score * 0.18
        + min(average_confidence, 100.0) * 0.08
        - inorganic_rate * 0.18
    )
    score = max(0, min(100, round(raw_score)))
    if score >= 80:
        label = "Rat tot"
    elif score >= 60:
        label = "On dinh"
    elif score >= 40:
        label = "Can cai thien"
    else:
        label = "Can theo doi"
    return EcoScoreDTO(
        score=score,
        label=label,
        recyclable_rate=recyclable_rate,
        inorganic_rate=inorganic_rate,
        organic_rate=organic_rate,
        consistency_score=consistency_score,
    )


def _device_status(runtime: AgentRuntime, owner_username: str | None) -> DeviceStatusDTO:
    status = runtime.status(include_devices=False)
    bins = runtime.bin_fullness()
    camera_ok = bool(status.camera.connected or status.camera.running)
    model_ok = bool(status.model.connected or status.model.running)
    uart_ok = bool(status.uart.connected or status.uart.running)
    online = camera_ok or model_ok or uart_ok
    if camera_ok and model_ok:
        status_label = "online"
        message = "Thiet bi dang san sang ghi nhan rac."
    elif online:
        status_label = "warning"
        message = "Thiet bi dang hoat dong mot phan; Admin nen kiem tra camera/UART/model."
    else:
        status_label = "offline"
        message = "Chua thay tin hieu thiet bi dang hoat dong."
    return DeviceStatusDTO(
        device_id=runtime.cfg.device.device_id,
        device_name=runtime.cfg.device.device_name,
        location=runtime.cfg.device.location,
        owner_username=owner_username or runtime.cfg.device.owner_username,
        online=online,
        status=status_label,
        message=message,
        last_active_at=datetime.now().isoformat() if online else None,
        bins=bins,
    )


def _history_items(rows) -> list[UserHistoryItemDTO]:
    items: list[UserHistoryItemDTO] = []
    for row in rows:
        category = _row_category(row)
        items.append(
            UserHistoryItemDTO(
                id=int(getattr(row, "id", 0) or 0),
                ts=str(getattr(row, "ts", "") or ""),
                cls_name=str(getattr(row, "cls_name", "") or ""),
                confidence=round(float(getattr(row, "conf", 0.0) or 0.0), 3),
                route_label=getattr(row, "route_label", None),
                bin_index=getattr(row, "bin_index", None),
                category=_category_slug(category),
                ack_status=getattr(row, "ack_status", None),
                device_id=getattr(row, "device_id", None),
                image_available=bool(
                    getattr(row, "annotated_path", None) or getattr(row, "image_path", None)
                ),
            )
        )
    return items


def _category_slug(category: WasteCategory) -> str:
    if category.code == ORGANIC.code:
        return "organic"
    if category.code == RECYCLABLE.code:
        return "recyclable"
    return "inorganic"


def _deepseek_model() -> str:
    return DEFAULT_DEEPSEEK_MODEL


def _advisor_payload(analytics: UserAnalyticsResponse) -> dict[str, object]:
    return {
        "range_days": analytics.range_days,
        "total": analytics.total,
        "today_total": analytics.today_total,
        "seven_day_total": analytics.seven_day_total,
        "thirty_day_total": analytics.thirty_day_total,
        "average_confidence": analytics.average_confidence,
        "eco_score": analytics.eco_score.model_dump(mode="json"),
        "device_status": analytics.device_status.model_dump(mode="json"),
        "comparison": analytics.comparison.model_dump(mode="json"),
        "route_totals": [item.model_dump(mode="json") for item in analytics.route_totals],
        "top_classes": [item.model_dump(mode="json") for item in analytics.top_classes[:8]],
        "yesterday": analytics.yesterday.model_dump(mode="json"),
        "daily": [item.model_dump(mode="json") for item in analytics.daily[-31:]],
        "monthly": [item.model_dump(mode="json") for item in analytics.monthly],
        "recent_classifications": [
            item.model_dump(mode="json") for item in analytics.recent_classifications[:12]
        ],
        "local_insights": [item.model_dump(mode="json") for item in analytics.insights],
    }


def _local_advisor_message(analytics: UserAnalyticsResponse) -> str:
    if not analytics.insights:
        return "Hay tiep tuc theo doi them vai ngay de he thong co du du lieu tu van."
    return " ".join(f"{item.title}: {item.message}" for item in analytics.insights[:3])


__all__ = [
    "ALLOWED_ANALYTICS_RANGES",
    "build_user_advisor",
    "build_user_analytics",
    "build_user_dashboard",
    "build_user_history",
]
