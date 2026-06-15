"""Post-inference filtering for duplicate detections and empty-tray artifacts."""

from __future__ import annotations

import cv2
import numpy as np

from app.core.events import Detection

PAPER_LIKE_CLASSES = {"Paper", "Paper bag"}


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


def find_ambiguous_organic_candidate(
    detections: list[Detection],
    *,
    max_primary_confidence: float,
    max_confidence_gap: float = 0.25,
    min_organic_confidence: float = 0.05,
    min_organic_ratio: float = 0.22,
) -> tuple[Detection, Detection] | None:
    """Find a paper-like prediction that is nearly tied with Organic."""
    paper_candidates = sorted(
        (
            detection
            for detection in detections
            if detection.cls_name in PAPER_LIKE_CLASSES
            and detection.conf <= max_primary_confidence
        ),
        key=lambda item: item.conf,
        reverse=True,
    )
    organic_candidates = [
        detection for detection in detections if detection.cls_name == "Organic"
    ]
    for paper in paper_candidates:
        for organic in organic_candidates:
            if organic.conf < min_organic_confidence:
                continue
            if paper.conf - organic.conf > max_confidence_gap:
                continue
            if organic.conf / max(paper.conf, 1e-6) < min_organic_ratio:
                continue
            if _same_physical_object(paper.xyxy, organic.xyxy, iou_threshold=0.70):
                return paper, organic
    return None


def is_uniform_empty_tray_artifact(
    frame_bgr: np.ndarray,
    detections: list[Detection],
    *,
    roi_xyxy: tuple[int, int, int, int] | None = None,
) -> bool:
    """Reject a full-tray box when the image contains no material detail."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] < 3 or not detections:
        return False
    height, width = frame_bgr.shape[:2]
    rx1, ry1, rx2, ry2 = _clamp_box(roi_xyxy or (0, 0, width, height), width, height)
    roi_area = max(1, (rx2 - rx1) * (ry2 - ry1))
    covers_tray = any(
        _intersection_area(detection.xyxy, (rx1, ry1, rx2, ry2)) / roi_area >= 0.65
        for detection in detections
    )
    if not covers_tray:
        return False

    crop = frame_bgr[ry1:ry2, rx1:rx2, :3]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 90)
    median = float(np.median(gray))
    strong_deviation = float(np.mean(np.abs(gray.astype(np.float32) - median) > 30.0))
    saturation_ratio = float(np.mean(hsv[:, :, 1] > 20))
    edge_ratio = float(np.count_nonzero(edges)) / float(max(1, edges.size))
    return saturation_ratio < 0.04 and strong_deviation < 0.08 and edge_ratio < 0.004


def _clamp_box(
    xyxy: tuple[int, int, int, int],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = xyxy
    x1 = max(0, min(int(x1), width - 1))
    y1 = max(0, min(int(y1), height - 1))
    x2 = max(x1 + 1, min(int(x2), width))
    y2 = max(y1 + 1, min(int(y2), height))
    return x1, y1, x2, y2


def _intersection_area(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> int:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    return max(0, min(ax2, bx2) - max(ax1, bx1)) * max(
        0, min(ay2, by2) - max(ay1, by1)
    )


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


__all__ = [
    "find_ambiguous_organic_candidate",
    "is_uniform_empty_tray_artifact",
    "suppress_overlapping_detections",
]
