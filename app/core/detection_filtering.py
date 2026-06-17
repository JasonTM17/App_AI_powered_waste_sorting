"""Post-inference filtering for duplicate detections and empty-tray artifacts."""

from __future__ import annotations

import cv2
import numpy as np

from app.core.events import Detection

PAPER_LIKE_CLASSES = {"Paper", "Paper bag"}
PREFERRED_DUPLICATE_SOURCES = {
    "manual_reference": 0,
    "visual_correction:crumpled_paper": 1,
    "visual_correction:eggshell": 1,
    "visual_correction:ceramic_dish": 1,
    "visual_correction:wooden_utensil": 1,
    "visual_correction:metal_utensil": 1,
    "visual_correction:plastic_bottle": 1,
    "visual_correction:leafy_organic": 1,
    "YOLO": 2,
    "kaggle_three_bin_classifier": 3,
}
UNKNOWN_CLASS_NAMES = {"Unknown object"}


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


def collapse_duplicate_physical_detections(
    detections: list[Detection],
    *,
    iou_threshold: float = 0.30,
) -> list[Detection]:
    """Merge boxes that are different labels for the same visible object."""
    clusters: list[list[Detection]] = []
    for detection in detections:
        for cluster in clusters:
            if any(
                _same_physical_object(
                    detection.xyxy,
                    item.xyxy,
                    iou_threshold=iou_threshold,
                )
                or _same_local_object(detection.xyxy, item.xyxy)
                for item in cluster
            ):
                cluster.append(detection)
                break
        else:
            clusters.append([detection])

    collapsed = [_best_duplicate_candidate(cluster) for cluster in clusters]
    return sorted(collapsed, key=lambda item: item.conf, reverse=True)


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
            if detection.cls_name in PAPER_LIKE_CLASSES and detection.conf <= max_primary_confidence
        ),
        key=lambda item: item.conf,
        reverse=True,
    )
    organic_candidates = [detection for detection in detections if detection.cls_name == "Organic"]
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
    return saturation_ratio < 0.04 and strong_deviation < 0.10 and edge_ratio < 0.004


def is_low_detail_empty_tray(
    frame_bgr: np.ndarray,
    detections: list[Detection] | None = None,
) -> bool:
    """Reject plain tray frames before fallback classification and dispatch."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] < 3 or frame_bgr.size == 0:
        return False
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 90)
    saturation_ratio = float(np.mean(hsv[:, :, 1] > 20))
    edge_ratio = float(np.count_nonzero(edges)) / float(max(1, edges.size))
    low_detail = (
        float(np.mean(gray)) > 140.0
        and saturation_ratio < 0.02
        and edge_ratio < 0.001
        and float(np.std(gray)) < 30.0
    )
    if not low_detail or not detections:
        return low_detail
    height, width = gray.shape[:2]
    frame_area = float(max(1, width * height))
    border_x = max(2, round(width * 0.02))
    border_y = max(2, round(height * 0.02))
    for detection in detections:
        x1, y1, x2, y2 = _clamp_box(detection.xyxy, width, height)
        coverage = ((x2 - x1) * (y2 - y1)) / frame_area
        touches_border = (
            x1 <= border_x or y1 <= border_y or x2 >= width - border_x or y2 >= height - border_y
        )
        if coverage >= 0.65 or (coverage <= 0.08 and touches_border):
            return True
    return False


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
    return max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))


def _box_area(xyxy: tuple[int, int, int, int]) -> int:
    x1, y1, x2, y2 = xyxy
    return max(0, x2 - x1) * max(0, y2 - y1)


def _same_local_object(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> bool:
    first_area = _box_area(first)
    second_area = _box_area(second)
    if first_area <= 0 or second_area <= 0:
        return False

    largest = first if first_area >= second_area else second
    smallest = second if first_area >= second_area else first
    lx1, ly1, lx2, ly2 = largest
    sx1, sy1, sx2, sy2 = smallest
    largest_width = max(1, lx2 - lx1)
    largest_height = max(1, ly2 - ly1)
    expand_x = max(10, round(largest_width * 0.12))
    expand_y = max(10, round(largest_height * 0.12))
    center_x = (sx1 + sx2) / 2.0
    center_y = (sy1 + sy2) / 2.0
    center_inside = (
        lx1 - expand_x <= center_x <= lx2 + expand_x
        and ly1 - expand_y <= center_y <= ly2 + expand_y
    )
    if not center_inside:
        return False

    intersection = _intersection_area(first, second)
    smaller_coverage = intersection / max(min(first_area, second_area), 1)
    if (
        smaller_coverage >= 0.42
        and min(first_area, second_area) / max(first_area, second_area) <= 0.82
    ):
        return True

    union_area = first_area + second_area - intersection
    return union_area / max(first_area, second_area) <= 1.72


def _best_duplicate_candidate(cluster: list[Detection]) -> Detection:
    def rank(detection: Detection) -> tuple[int, int, float]:
        source_rank = PREFERRED_DUPLICATE_SOURCES.get(detection.source, 4)
        known_rank = 1 if detection.cls_name in UNKNOWN_CLASS_NAMES else 0
        return source_rank, known_rank, -float(detection.conf)

    return min(cluster, key=rank)


def _same_physical_object(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
    *,
    iou_threshold: float,
) -> bool:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    intersection = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
    first_area = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    second_area = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = first_area + second_area - intersection
    iou = intersection / max(union, 1)
    smaller_coverage = intersection / max(min(first_area, second_area), 1)
    if iou >= iou_threshold or smaller_coverage >= 0.65:
        return True

    if smaller_coverage < 0.38:
        return False
    larger = first if first_area >= second_area else second
    smaller = second if first_area >= second_area else first
    lx1, ly1, lx2, ly2 = larger
    sx1, sy1, sx2, sy2 = smaller
    center_x = (sx1 + sx2) / 2.0
    center_y = (sy1 + sy2) / 2.0
    larger_width = max(1, lx2 - lx1)
    larger_height = max(1, ly2 - ly1)
    expand_x = max(8, round(larger_width * 0.10))
    expand_y = max(8, round(larger_height * 0.10))
    center_inside = (
        lx1 - expand_x <= center_x <= lx2 + expand_x
        and ly1 - expand_y <= center_y <= ly2 + expand_y
    )
    area_ratio = min(first_area, second_area) / max(first_area, second_area)
    return center_inside and area_ratio <= 0.75


__all__ = [
    "collapse_duplicate_physical_detections",
    "find_ambiguous_organic_candidate",
    "is_low_detail_empty_tray",
    "is_uniform_empty_tray_artifact",
    "suppress_overlapping_detections",
]
