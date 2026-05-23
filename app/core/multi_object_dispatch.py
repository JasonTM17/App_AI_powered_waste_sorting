"""Helpers for blocking hardware dispatch when multiple objects are visible."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from app.core.events import TrackedDetection


@dataclass(frozen=True)
class MultiObjectDecision:
    allowed: bool
    class_names: tuple[str, ...] = ()
    reason: str = ""
    object_count: int = 0


def _roi_bounds(
    roi: object | None,
    width: int,
    height: int,
) -> tuple[int, int, int, int] | None:
    if width <= 0 or height <= 0:
        return None
    if roi is None or not bool(getattr(roi, "enabled", False)):
        return 0, 0, width, height
    roi_x = max(0, int(getattr(roi, "x", 0)))
    roi_y = max(0, int(getattr(roi, "y", 0)))
    roi_w = max(0, int(getattr(roi, "width", 0)))
    roi_h = max(0, int(getattr(roi, "height", 0)))
    if roi_w <= 0 or roi_h <= 0:
        return None
    return (
        roi_x,
        roi_y,
        min(width, roi_x + roi_w),
        min(height, roi_y + roi_h),
    )


def _foreground_boxes(
    frame_bgr: np.ndarray,
    *,
    roi: object | None,
    min_area_ratio: float,
) -> tuple[tuple[int, int, int, int], ...]:
    try:
        import cv2
    except Exception:
        return ()
    if frame_bgr.size == 0:
        return ()
    height, width = frame_bgr.shape[:2]
    bounds = _roi_bounds(roi, width, height)
    if bounds is None:
        return ()
    x1, y1, x2, y2 = bounds
    crop = frame_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return ()

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    _h, saturation, value = cv2.split(hsv)
    colored = (saturation > 42) & (value > 35) & (value < 250)
    dark = value < 120
    mask = np.where(colored | dark, 255, 0).astype("uint8")

    kernel = np.ones((5, 5), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)

    crop_area = float(crop.shape[0] * crop.shape[1])
    min_area = max(256, int(crop_area * min_area_ratio))
    boxes: list[tuple[int, int, int, int, int]] = []
    crop_width = crop.shape[1]
    crop_height = crop.shape[0]
    for idx in range(1, count):
        area = int(stats[idx, cv2.CC_STAT_AREA])
        if area < min_area:
            continue
        left = int(stats[idx, cv2.CC_STAT_LEFT])
        top = int(stats[idx, cv2.CC_STAT_TOP])
        box_width = int(stats[idx, cv2.CC_STAT_WIDTH])
        box_height = int(stats[idx, cv2.CC_STAT_HEIGHT])
        if box_width <= 0 or box_height <= 0:
            continue
        right = left + box_width
        bottom = top + box_height
        touch_count = sum(
            (
                left <= 1,
                top <= 1,
                right >= crop_width - 1,
                bottom >= crop_height - 1,
            )
        )
        box_area = float(box_width * box_height)
        coverage = box_area / max(crop_area, 1.0)
        if coverage > 0.85:
            continue
        if touch_count >= 2 and coverage < 0.2:
            continue
        boxes.append((x1 + left, y1 + top, x1 + right, y1 + bottom, area))

    boxes.sort(key=lambda item: item[4], reverse=True)
    return tuple((left, top, right, bottom) for left, top, right, bottom, _area in boxes[:10])


def evaluate_foreground_multi_object_dispatch(
    frame_bgr: np.ndarray,
    *,
    roi: object | None,
    max_objects: int = 1,
    min_area_ratio: float = 0.003,
) -> MultiObjectDecision:
    """Block dispatch when the ROI clearly contains more than one foreground object."""
    if max_objects <= 0:
        return MultiObjectDecision(allowed=True)
    boxes = _foreground_boxes(frame_bgr, roi=roi, min_area_ratio=min_area_ratio)
    if len(boxes) <= max_objects:
        return MultiObjectDecision(allowed=True, object_count=len(boxes))
    count = len(boxes)
    return MultiObjectDecision(
        allowed=False,
        class_names=(f"{count} visible objects",),
        reason=f"multiple waste types ({count} visible objects)",
        object_count=count,
    )


def foreground_object_boxes(
    frame_bgr: np.ndarray,
    *,
    roi: object | None,
    min_area_ratio: float = 0.003,
) -> tuple[tuple[int, int, int, int], ...]:
    """Return foreground object candidates for UI annotation suggestions."""
    return _foreground_boxes(frame_bgr, roi=roi, min_area_ratio=min_area_ratio)


def evaluate_single_class_dispatch(
    tracked: list[TrackedDetection],
    *,
    in_roi: Callable[[tuple[int, int, int, int]], bool],
    max_objects: int = 1,
    max_classes: int = 1,
) -> MultiObjectDecision:
    """Allow dispatch only when the ROI contains one sortable object."""
    visible = [item for item in tracked if in_roi(item.detection.xyxy)]
    if max_objects > 0 and len(visible) > max_objects:
        return MultiObjectDecision(
            allowed=False,
            class_names=tuple(sorted({item.detection.cls_name for item in visible})),
            reason="multiple waste types",
            object_count=len(visible),
        )
    if max_classes <= 0:
        return MultiObjectDecision(allowed=True, object_count=len(visible))
    class_names = sorted(
        {
            item.detection.cls_name
            for item in visible
        }
    )
    if len(class_names) <= max_classes:
        return MultiObjectDecision(
            allowed=True,
            class_names=tuple(class_names),
            object_count=len(visible),
        )
    return MultiObjectDecision(
        allowed=False,
        class_names=tuple(class_names),
        reason="multiple waste types",
        object_count=len(visible),
    )


__all__ = [
    "MultiObjectDecision",
    "evaluate_foreground_multi_object_dispatch",
    "evaluate_single_class_dispatch",
    "foreground_object_boxes",
]
