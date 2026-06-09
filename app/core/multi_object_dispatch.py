"""Helpers for blocking hardware dispatch when multiple waste types are visible."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.core.events import TrackedDetection


@dataclass(frozen=True)
class MultiObjectDecision:
    allowed: bool
    class_names: tuple[str, ...] = ()
    reason: str = ""


def evaluate_single_class_dispatch(
    tracked: list[TrackedDetection],
    *,
    in_roi: Callable[[tuple[int, int, int, int]], bool],
    max_classes: int = 1,
) -> MultiObjectDecision:
    """Allow dispatch only when at most max distinct classes are visible in ROI."""
    if max_classes <= 0:
        return MultiObjectDecision(allowed=True)
    class_names = sorted(
        {
            item.detection.cls_name
            for item in tracked
            if in_roi(item.detection.xyxy)
        }
    )
    if len(class_names) <= max_classes:
        return MultiObjectDecision(allowed=True, class_names=tuple(class_names))
    return MultiObjectDecision(
        allowed=False,
        class_names=tuple(class_names),
        reason="multiple waste types",
    )


__all__ = ["MultiObjectDecision", "evaluate_single_class_dispatch"]
