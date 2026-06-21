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
    foreground_count: int = 0
    reference_count: int = 0
    unmatched_foreground_count: int = 0


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
    reference_boxes: tuple[tuple[int, int, int, int], ...] = (),
) -> MultiObjectDecision:
    """Block dispatch when the ROI clearly contains more than one foreground object."""
    if max_objects <= 0:
        return MultiObjectDecision(allowed=True)
    boxes = _foreground_boxes(frame_bgr, roi=roi, min_area_ratio=min_area_ratio)
    object_boxes = _cluster_foreground_boxes(boxes)
    references = tuple(reference_boxes)
    contained_counts = tuple(
        _contained_independent_object_count(object_boxes, reference)
        for reference in references
    )
    unmatched_count = sum(
        1
        for foreground_box in object_boxes
        if not any(
            _foreground_belongs_to_reference(foreground_box, reference)
            for reference in references
        )
    )
    reference_object_count = sum(max(1, count) for count in contained_counts)
    count = reference_object_count + unmatched_count if references else len(object_boxes)
    decision_meta = {
        "object_count": count,
        "foreground_count": len(boxes),
        "reference_count": len(references),
        "unmatched_foreground_count": unmatched_count,
    }
    if count <= max_objects:
        return MultiObjectDecision(allowed=True, **decision_meta)
    return MultiObjectDecision(
        allowed=False,
        class_names=(f"{count} visible objects",),
        reason=f"multiple waste types ({count} visible objects)",
        **decision_meta,
    )


def _contained_independent_object_count(
    boxes: tuple[tuple[int, int, int, int], ...],
    reference: tuple[int, int, int, int],
) -> int:
    """Count clearly separate foreground objects hidden by one loose detector box."""
    rx1, ry1, rx2, ry2 = reference
    reference_area = _box_area(reference)
    if reference_area <= 0:
        return 0

    contained = [
        box
        for box in boxes
        if rx1 <= (box[0] + box[2]) / 2.0 <= rx2
        and ry1 <= (box[1] + box[3]) / 2.0 <= ry2
        and _box_area(box) >= reference_area * 0.025
    ]
    if len(contained) < 2:
        return len(contained)

    independent: list[tuple[int, int, int, int]] = []
    for candidate in sorted(contained, key=_box_area, reverse=True):
        if all(
            _foreground_objects_clearly_separate(candidate, accepted, reference)
            for accepted in independent
        ):
            independent.append(candidate)
    return len(independent)


def _foreground_objects_clearly_separate(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
    reference: tuple[int, int, int, int],
) -> bool:
    """Reject highlight/shadow fragments while preserving genuinely separate items."""
    first_area = _box_area(first)
    second_area = _box_area(second)
    if min(first_area, second_area) / max(first_area, second_area, 1) < 0.12:
        return False

    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    gap_x = max(ax1 - bx2, bx1 - ax2, 0)
    gap_y = max(ay1 - by2, by1 - ay2, 0)
    reference_width = max(1, reference[2] - reference[0])
    reference_height = max(1, reference[3] - reference[1])
    clear_horizontal_gap = gap_x >= max(8, round(reference_width * 0.025))
    clear_vertical_gap = gap_y >= max(8, round(reference_height * 0.025))
    return clear_horizontal_gap or clear_vertical_gap


def _cluster_foreground_boxes(
    boxes: tuple[tuple[int, int, int, int], ...],
) -> tuple[tuple[int, int, int, int], ...]:
    clusters: list[list[tuple[int, int, int, int]]] = [[box] for box in boxes]
    changed = True
    while changed:
        changed = False
        for first_index in range(len(clusters)):
            for second_index in range(first_index + 1, len(clusters)):
                if _foreground_clusters_same_object(
                    clusters[first_index],
                    clusters[second_index],
                ):
                    clusters[first_index].extend(clusters[second_index])
                    del clusters[second_index]
                    changed = True
                    break
            if changed:
                break
    return tuple(_union_boxes(cluster) for cluster in clusters)


def _foreground_clusters_same_object(
    first: list[tuple[int, int, int, int]],
    second: list[tuple[int, int, int, int]],
) -> bool:
    if any(
        _foreground_fragments_same_object(first_box, second_box)
        for first_box in first
        for second_box in second
    ):
        return True
    # A long object can be split into three pieces where neither endpoint
    # overlaps the other directly. Re-check merged cluster hulls so a pen or
    # utensil stays one object after its small middle fragments are joined.
    return _foreground_fragments_same_object(_union_boxes(first), _union_boxes(second))


def _foreground_fragments_same_object(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> bool:
    first_area = _box_area(first)
    second_area = _box_area(second)
    if first_area <= 0 or second_area <= 0:
        return False
    larger = first if first_area >= second_area else second
    smaller = second if first_area >= second_area else first
    if _touching_foreground_fragments_same_object(first, second):
        return True
    if _elongated_foreground_fragments_same_object(first, second):
        return True
    if min(first_area, second_area) / max(first_area, second_area) > 0.35:
        return False
    return _small_foreground_fragment_belongs_to_object(smaller, larger)


def _touching_foreground_fragments_same_object(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> bool:
    """Join adjacent halves split by a bright crease on one bulky object."""
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    first_width = max(1, ax2 - ax1)
    first_height = max(1, ay2 - ay1)
    second_width = max(1, bx2 - bx1)
    second_height = max(1, by2 - by1)
    gap_x = max(ax1 - bx2, bx1 - ax2, 0)
    gap_y = max(ay1 - by2, by1 - ay2, 0)
    horizontal_overlap = max(0, min(ax2, bx2) - max(ax1, bx1))
    vertical_overlap = max(0, min(ay2, by2) - max(ay1, by1))
    horizontal_ratio = horizontal_overlap / min(first_width, second_width)
    vertical_ratio = vertical_overlap / min(first_height, second_height)
    close_x = max(3, round(max(first_width, second_width) * 0.02))
    close_y = max(3, round(max(first_height, second_height) * 0.02))
    return (gap_x <= close_x and vertical_ratio >= 0.72) or (
        gap_y <= close_y and horizontal_ratio >= 0.72
    )


def _box_area(box: tuple[int, int, int, int]) -> int:
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def _union_boxes(
    boxes: list[tuple[int, int, int, int]],
) -> tuple[int, int, int, int]:
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _elongated_foreground_fragments_same_object(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> bool:
    """Join split foreground pieces of one long pen/utensil without merging two bulky items."""
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    union = _union_boxes([first, second])
    ux1, uy1, ux2, uy2 = union
    union_width = max(1, ux2 - ux1)
    union_height = max(1, uy2 - uy1)
    aspect = union_width / union_height
    horizontal_shape = aspect >= 3.8
    vertical_shape = aspect <= 0.26
    if not horizontal_shape and not vertical_shape:
        return False

    first_width = max(1, ax2 - ax1)
    first_height = max(1, ay2 - ay1)
    second_width = max(1, bx2 - bx1)
    second_height = max(1, by2 - by1)
    horizontal_overlap = max(0, min(ax2, bx2) - max(ax1, bx1))
    vertical_overlap = max(0, min(ay2, by2) - max(ay1, by1))
    gap_x = max(ax1 - bx2, bx1 - ax2, 0)
    gap_y = max(ay1 - by2, by1 - ay2, 0)

    if horizontal_shape:
        vertical_ratio = vertical_overlap / min(first_height, second_height)
        close_gap = max(24, min(96, round(union_width * 0.16)))
        center_gap_y = abs(((ay1 + ay2) / 2.0) - ((by1 + by2) / 2.0))
        center_aligned = center_gap_y <= max(first_height, second_height) * 0.85
        return gap_x <= close_gap and (
            vertical_ratio >= 0.45
            or (vertical_ratio >= 0.15 and center_aligned)
        )

    horizontal_ratio = horizontal_overlap / min(first_width, second_width)
    close_gap = max(24, min(96, round(union_height * 0.16)))
    return horizontal_ratio >= 0.45 and gap_y <= close_gap


def _foreground_belongs_to_reference(
    foreground: tuple[int, int, int, int],
    reference: tuple[int, int, int, int],
) -> bool:
    fx1, fy1, fx2, fy2 = foreground
    rx1, ry1, rx2, ry2 = reference
    reference_width = max(0, rx2 - rx1)
    reference_height = max(0, ry2 - ry1)
    # Transparent or glossy objects often produce disconnected highlights just
    # outside the detector box. Keep a bounded halo so those fragments still
    # belong to the detected object without absorbing a clearly separate item.
    expand_x = min(32, max(4, round(reference_width * 0.10)))
    expand_y = min(32, max(4, round(reference_height * 0.10)))
    center_x = (fx1 + fx2) / 2.0
    center_y = (fy1 + fy2) / 2.0
    center_inside = (
        rx1 - expand_x <= center_x <= rx2 + expand_x
        and ry1 - expand_y <= center_y <= ry2 + expand_y
    )
    if center_inside:
        return True
    intersection = max(0, min(fx2, rx2) - max(fx1, rx1)) * max(
        0, min(fy2, ry2) - max(fy1, ry1)
    )
    foreground_area = max(1, max(0, fx2 - fx1) * max(0, fy2 - fy1))
    if intersection / foreground_area >= 0.5:
        return True

    # Thin glossy utensils, pens, and bottle highlights often split into a
    # shadow/highlight component just outside the detector box. If that
    # fragment is small, close, and aligned with the detected object, keep it
    # attached to the same object so the hardware path is not blocked forever.
    reference_area = max(1, reference_width * reference_height)
    if foreground_area > reference_area * 0.50:
        return False
    horizontal_overlap = max(0, min(fx2, rx2) - max(fx1, rx1))
    vertical_overlap = max(0, min(fy2, ry2) - max(fy1, ry1))
    foreground_width = max(1, fx2 - fx1)
    foreground_height = max(1, fy2 - fy1)
    horizontal_ratio = horizontal_overlap / min(foreground_width, max(1, reference_width))
    vertical_ratio = vertical_overlap / min(foreground_height, max(1, reference_height))
    gap_x = max(rx1 - fx2, fx1 - rx2, 0)
    gap_y = max(ry1 - fy2, fy1 - ry2, 0)
    close_gap = max(18, round(max(reference_width, reference_height) * 0.08))
    if gap_x <= close_gap and vertical_ratio >= 0.35:
        return True
    return gap_y <= close_gap and horizontal_ratio >= 0.35


def _small_foreground_fragment_belongs_to_object(
    foreground: tuple[int, int, int, int],
    reference: tuple[int, int, int, int],
) -> bool:
    fx1, fy1, fx2, fy2 = foreground
    rx1, ry1, rx2, ry2 = reference
    reference_width = max(1, rx2 - rx1)
    reference_height = max(1, ry2 - ry1)
    foreground_width = max(1, fx2 - fx1)
    foreground_height = max(1, fy2 - fy1)
    horizontal_overlap = max(0, min(fx2, rx2) - max(fx1, rx1))
    vertical_overlap = max(0, min(fy2, ry2) - max(fy1, ry1))
    horizontal_ratio = horizontal_overlap / min(foreground_width, reference_width)
    vertical_ratio = vertical_overlap / min(foreground_height, reference_height)
    gap_x = max(rx1 - fx2, fx1 - rx2, 0)
    gap_y = max(ry1 - fy2, fy1 - ry2, 0)
    foreground_aspect = foreground_width / foreground_height
    reference_aspect = reference_width / reference_height
    foreground_is_horizontal_item = foreground_aspect >= 3.0
    foreground_is_vertical_item = foreground_aspect <= 1 / 3.0
    reference_is_bulky = 1 / 3.0 < reference_aspect < 3.0
    # A pen below a spoon is a distinct long item, not a highlight fragment of
    # the spoon. Preserve thin satellites only when they overlap the bulky
    # object's silhouette instead of sitting across a visible background gap.
    if reference_is_bulky:
        if foreground_is_horizontal_item and gap_y > 0:
            return False
        if foreground_is_vertical_item and gap_x > 0:
            return False
    # Crumpled paper and glossy trash often appear as one dominant blob with
    # smaller fold/shadow fragments separated by bright creases. Keep a wider
    # attachment band for those small satellites, while the caller still keeps
    # similarly-sized objects split before this helper is reached.
    close_gap = max(18, min(64, round(max(reference_width, reference_height) * 0.20)))
    if gap_x <= close_gap and vertical_ratio >= 0.55:
        return True
    return gap_y <= close_gap and horizontal_ratio >= 0.55


def foreground_object_boxes(
    frame_bgr: np.ndarray,
    *,
    roi: object | None,
    min_area_ratio: float = 0.003,
) -> tuple[tuple[int, int, int, int], ...]:
    """Return foreground object candidates for UI annotation suggestions."""
    return _foreground_boxes(frame_bgr, roi=roi, min_area_ratio=min_area_ratio)


def foreground_object_clusters(
    frame_bgr: np.ndarray,
    *,
    roi: object | None,
    min_area_ratio: float = 0.003,
) -> tuple[tuple[int, int, int, int], ...]:
    """Return foreground candidates clustered into likely physical objects."""
    return _cluster_foreground_boxes(
        _foreground_boxes(frame_bgr, roi=roi, min_area_ratio=min_area_ratio)
    )


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
    "foreground_object_clusters",
]
