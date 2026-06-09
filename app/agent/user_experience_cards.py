"""Local read-only notification, challenge, and community projections."""

from __future__ import annotations

from app.agent.schemas import (
    UserChallengeDTO,
    UserCommunityCardDTO,
    UserExperienceResponse,
    UserLeaderboardRowDTO,
    UserNotificationDTO,
)
from app.core.waste_categories import INORGANIC, RECYCLABLE


def build_user_experience_response(analytics, generated_at: str) -> UserExperienceResponse:
    return UserExperienceResponse(
        generated_at=generated_at,
        range_days=analytics.range_days,
        notifications=_notifications(analytics, generated_at),
        challenges=_challenges(analytics),
        leaderboard=_leaderboard(analytics),
        community_cards=_community_cards(analytics),
        quick_actions=[
            {"label": "Xem bao cao", "route": "/user/reports"},
            {"label": "Hoi EcoPet", "route": "/user/ecopet"},
            {"label": "Kiem tra thiet bi", "route": "/user/device"},
        ],
    )


def _notifications(analytics, generated_at: str) -> list[UserNotificationDTO]:
    items: list[UserNotificationDTO] = []
    if analytics.total == 0:
        items.append(
            UserNotificationDTO(
                id="empty-history",
                title="Chua co du lieu trong khoang nay",
                message="Hay bo rac qua may de dashboard tao bieu do va loi khuyen chinh xac hon.",
                severity="info",
                created_at=generated_at,
                route="/user/dashboard",
                action_label="Xem tong quan",
            )
        )
    if analytics.device_status.status != "online":
        items.append(
            UserNotificationDTO(
                id="device-status",
                title="Thiet bi can kiem tra",
                message=analytics.device_status.message,
                severity="warning",
                created_at=generated_at,
                route="/user/device",
                action_label="Xem thiet bi",
            )
        )
    items.extend(_bin_notifications(analytics, generated_at))
    if analytics.total and analytics.eco_score.inorganic_rate >= 55:
        items.append(
            UserNotificationDTO(
                id="inorganic-rate",
                title="Rac vo co dang chiem ti le cao",
                message="EcoPet goi y xem lai thoi quen do dung mot lan trong vai ngay toi.",
                severity="warning",
                created_at=generated_at,
                route="/user/advice",
                action_label="Xem loi khuyen",
            )
        )
    return items[:6]


def _bin_notifications(analytics, generated_at: str) -> list[UserNotificationDTO]:
    notifications: list[UserNotificationDTO] = []
    for bin_item in analytics.bins:
        if bin_item.percent >= 90:
            severity = "danger"
        elif bin_item.percent >= 75:
            severity = "warning"
        else:
            continue
        notifications.append(
            UserNotificationDTO(
                id=f"bin-{bin_item.bin_index}",
                title=f"Thung {bin_item.bin_index} dang day {bin_item.percent}%",
                message=f"{bin_item.label} can duoc xu ly som de tranh tran thung.",
                severity=severity,
                created_at=generated_at,
                route="/user/device",
                action_label="Xem thung",
            )
        )
    return notifications


def _challenges(analytics) -> list[UserChallengeDTO]:
    recyclable = _route_count(analytics, RECYCLABLE.code)
    inorganic = _route_count(analytics, INORGANIC.code)
    active_days = sum(1 for item in analytics.daily if item.total > 0)
    return [
        UserChallengeDTO(
            id="recycle-10",
            title="10 luot tai che sach",
            description="Tich luy cac mon thuoc nhom tai che trong ky nay.",
            progress=min(float(recyclable), 10.0),
            target=10.0,
            reward_label="Huy hieu Tai che",
            completed=recyclable >= 10,
        ),
        UserChallengeDTO(
            id="seven-day-streak",
            title="Duy tri 7 ngay co du lieu",
            description="Moi ngay ghi nhan it nhat mot luot phan loai.",
            progress=min(float(active_days), 7.0),
            target=7.0,
            unit="ngay",
            reward_label="Chuoi xanh",
            completed=active_days >= 7,
        ),
        UserChallengeDTO(
            id="less-inorganic",
            title="Giam rac vo co",
            description="Giu rac vo co duoi 40% tong luot phan loai.",
            progress=max(0.0, float(analytics.total - inorganic)),
            target=max(1.0, float(analytics.total)),
            reward_label="Thoi quen ben vung",
            completed=analytics.total > 0 and analytics.eco_score.inorganic_rate <= 40,
        ),
    ]


def _leaderboard(analytics) -> list[UserLeaderboardRowDTO]:
    rows = [
        UserLeaderboardRowDTO(
            rank=0,
            label="Ban",
            score=analytics.eco_score.score,
            detail=f"{analytics.total} luot trong {analytics.range_days} ngay",
            current_user=True,
        ),
        UserLeaderboardRowDTO(rank=0, label="Muc tieu xanh", score=80, detail="Moc nen dat"),
        UserLeaderboardRowDTO(
            rank=0,
            label="Trung binh thiet bi",
            score=max(45, min(75, analytics.eco_score.score - 5)),
            detail="Benchmark local",
        ),
    ]
    rows.sort(key=lambda item: item.score, reverse=True)
    return [item.model_copy(update={"rank": index}) for index, item in enumerate(rows, start=1)]


def _community_cards(analytics) -> list[UserCommunityCardDTO]:
    if analytics.total == 0:
        return [
            UserCommunityCardDTO(
                id="welcome",
                title="Bat dau nhat ky xanh",
                message="Khi co du lieu, Eco-Share se tao the chia se thanh tich local.",
                metric="0 luot",
                tone="neutral",
            )
        ]
    recyclable = _route_count(analytics, RECYCLABLE.code)
    return [
        UserCommunityCardDTO(
            id="eco-score",
            title="Eco Score cua toi",
            message=f"Ban dang dat {analytics.eco_score.score}/100 diem trong ky nay.",
            metric=f"{analytics.eco_score.score}/100",
            share_text="Toi dang theo doi thoi quen phan loai rac voi Trash Sorter Pro.",
            tone="success" if analytics.eco_score.score >= 70 else "warning",
        ),
        UserCommunityCardDTO(
            id="recycle-count",
            title="Luot tai che",
            message="Cac mon tai che duoc ghi nhan rieng de ban de theo doi.",
            metric=f"{recyclable} luot",
            share_text=f"Toi da co {recyclable} luot tai che trong ky nay.",
            tone="success",
        ),
        UserCommunityCardDTO(
            id="yesterday",
            title="Hom qua ban da bo gi",
            message=f"He thong ghi nhan {analytics.yesterday.total} luot phan loai hom qua.",
            metric=f"{analytics.yesterday.total} luot",
            tone="neutral",
        ),
    ]


def _route_count(analytics, command: str) -> int:
    return next((item.count for item in analytics.route_totals if item.command == command), 0)


__all__ = ["build_user_experience_response"]
