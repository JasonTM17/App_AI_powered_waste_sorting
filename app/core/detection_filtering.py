"""Post-inference filtering for duplicate detections of the same physical object."""

from __future__ import annotations

from app.core.events import Detection


def suppress_overlapping_detections(
    detections: list[Detection],
    *,
    iou_threshold: float = 0.75,
) -> list[Detection]:
    """Keep the strongest label when several boxes describe one object."""
    kept: list[Detection] = []
    for detection in sorted(detections, key=lambda item: item.conf, reverse=True):
        if any(
            _same_physical_object(
                detection.xyxy,
                item.xyxy,
                iou_threshold=iou_threshold,
            )
            for item in kept
        ):
            continue
        kept.append(detection)
    return kept


def _same_physical_object(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
    *,
    iou_threshold: float,
) -> bool:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    intersection = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(
        0, min(ay2, by2) - max(ay1, by1)
    )
    first_area = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    second_area = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = first_area + second_area - intersection
    iou = intersection / max(union, 1)
    smaller_coverage = intersection / max(min(first_area, second_area), 1)
    return iou >= iou_threshold or smaller_coverage >= 0.85


__all__ = ["suppress_overlapping_detections"]
