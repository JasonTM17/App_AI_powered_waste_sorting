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
    "visual_correction:battery": 1,
    "visual_correction:pen": 1,
    "visual_correction:plastic_bottle": 1,
    "visual_correction:leafy_organic": 1,
    "YOLO": 2,
    "kaggle_three_bin_classifier": 3,
}
UNKNOWN_CLASS_NAMES = {"Unknown object"}
BOTTLE_LIKE_CLASSES = {"Plastic bottle", "Glass bottle", "Milk bottle"}


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


def collapse_single_object_scene_detections(
    frame_bgr: np.ndarray,
    detections: list[Detection],
    *,
    min_large_area_ratio: float = 0.16,
) -> list[Detection]:
    """Collapse nested/nearby boxes when they are almost certainly one object.

    Blurry close-up camera frames can make YOLO return one large object box plus
    smaller label/cap/body boxes around the same bottle or can. Those duplicate
    boxes make the UI look unstable and can block auto-sort as "multi object".
    This keeps separate side-by-side objects, but folds boxes whose centers sit
    inside the same large physical object.
    """
    if len(detections) <= 1 or frame_bgr.ndim < 2:
        return detections
    height, width = frame_bgr.shape[:2]
    frame_area = float(max(1, width * height))
    clusters: list[list[Detection]] = []
    for detection in detections:
        for cluster in clusters:
            if any(
                _same_physical_object(detection.xyxy, item.xyxy, iou_threshold=0.38)
                or _same_large_scene_object(
                    detection.xyxy,
                    item.xyxy,
                    frame_area=frame_area,
                    min_large_area_ratio=min_large_area_ratio,
                )
                or _same_large_bottle_edge_fragment(
                    detection,
                    item,
                    frame_width=width,
                )
                for item in cluster
            ):
                cluster.append(detection)
                break
        else:
            clusters.append([detection])
    return sorted(
        (
            _collapse_single_object_scene_cluster(cluster, frame_width=width)
            for cluster in clusters
        ),
        key=lambda item: item.conf,
        reverse=True,
    )


def merge_fragmented_same_label_detections(
    detections: list[Detection],
    *,
    foreground_object_count: int | None = None,
) -> list[Detection]:
    """Merge split boxes from one physical object before multi-object safety.

    A detector can draw separate boxes around the cap/body/tip of a pen,
    battery, bottle, utensil, cable, or other elongated waste. Camera blur can
    also split one object into several foreground components, so foreground
    count is advisory: boxes still have to share the model class and be close
    and aligned before being merged. Operator labels may legitimately fluctuate
    between two fragments; the strongest detection supplies the final label.
    """
    _ = foreground_object_count
    clusters: list[list[Detection]] = []
    for detection in detections:
        for cluster in clusters:
            if all(
                item.cls_name == detection.cls_name
                and _fragmented_parts_of_one_object(item.xyxy, detection.xyxy)
                for item in cluster
            ):
                cluster.append(detection)
                break
        else:
            clusters.append([detection])
    return [
        cluster[0] if len(cluster) == 1 else _merge_fragment_cluster(cluster)
        for cluster in clusters
    ]


def _merge_fragment_cluster(cluster: list[Detection]) -> Detection:
    strongest = _best_duplicate_candidate(cluster)
    return Detection(
        cls_id=strongest.cls_id,
        cls_name=strongest.cls_name,
        conf=max(item.conf for item in cluster),
        xyxy=(
            min(item.xyxy[0] for item in cluster),
            min(item.xyxy[1] for item in cluster),
            max(item.xyxy[2] for item in cluster),
            max(item.xyxy[3] for item in cluster),
        ),
        source=strongest.source,
        operator_label=strongest.operator_label,
    )


def _fragmented_parts_of_one_object(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> bool:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    union_width = max(ax2, bx2) - min(ax1, bx1)
    union_height = max(ay2, by2) - min(ay1, by1)
    if union_width <= 0 or union_height <= 0:
        return False
    aspect = union_width / union_height
    horizontal = aspect >= 2.0
    vertical = aspect <= 1 / 2.0
    if not horizontal and not vertical:
        return False
    gap_x = max(ax1 - bx2, bx1 - ax2, 0)
    gap_y = max(ay1 - by2, by1 - ay2, 0)
    overlap_x = max(0, min(ax2, bx2) - max(ax1, bx1))
    overlap_y = max(0, min(ay2, by2) - max(ay1, by1))
    if horizontal:
        min_height = max(1, min(ay2 - ay1, by2 - by1))
        first_width = max(1, ax2 - ax1)
        second_width = max(1, bx2 - bx1)
        first_center_y = (ay1 + ay2) / 2.0
        second_center_y = (by1 + by2) / 2.0
        # A glossy/transparent object can disappear in the middle of the camera
        # frame, leaving only two ends as boxes. Allow a wider gap for
        # elongated, aligned parts; keep it proportional to detected material so
        # two separate objects placed far apart remain blocked as multi-object.
        close_gap = max(40, round(union_width * 0.45))
        if aspect >= 3.0:
            close_gap = max(close_gap, min(640, round((first_width + second_width) * 1.2)))
        aligned_long_parts = (
            aspect >= 3.0
            and abs(first_center_y - second_center_y) <= union_height * 0.75
        )
        return gap_x <= close_gap and (
            overlap_y / min_height >= 0.30 or aligned_long_parts
        )
    min_width = max(1, min(ax2 - ax1, bx2 - bx1))
    first_height = max(1, ay2 - ay1)
    second_height = max(1, by2 - by1)
    close_gap = max(40, round(union_height * 0.45))
    if aspect <= 1 / 3.0:
        close_gap = max(close_gap, min(640, round((first_height + second_height) * 1.2)))
    return gap_y <= close_gap and overlap_x / min_width >= 0.30


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


def is_verified_empty_tray(
    frame_bgr: np.ndarray,
    detections: list[Detection] | None = None,
    *,
    roi_xyxy: tuple[int, int, int, int] | None = None,
) -> bool:
    """Confirm a visibly empty tray despite dark rails or full-frame false boxes."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] < 3 or frame_bgr.size == 0:
        return False
    height, width = frame_bgr.shape[:2]
    x1, y1, x2, y2 = _clamp_box(roi_xyxy or (0, 0, width, height), width, height)
    roi_width = x2 - x1
    roi_height = y2 - y1
    inset_x = max(1, round(roi_width * 0.08))
    inset_y = max(1, round(roi_height * 0.08))
    if roi_width <= inset_x * 2 or roi_height <= inset_y * 2:
        return False
    crop = frame_bgr[y1 + inset_y : y2 - inset_y, x1 + inset_x : x2 - inset_x, :3]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 30, 90)
    median = float(np.median(gray))
    saturation_ratio = float(np.mean(hsv[:, :, 1] > 20))
    edge_ratio = float(np.count_nonzero(edges)) / float(max(1, edges.size))
    strong_deviation = float(np.mean(np.abs(gray.astype(np.float32) - median) > 30.0))
    visually_empty = (
        float(np.mean(gray)) > 165.0
        and float(np.std(gray)) < 22.0
        and saturation_ratio < 0.015
        and edge_ratio < 0.0015
        and strong_deviation < 0.05
    )
    if not visually_empty or not detections:
        return visually_empty

    roi_area = float(max(1, roi_width * roi_height))
    for detection in detections:
        box = _clamp_box(detection.xyxy, width, height)
        coverage = _intersection_area(box, (x1, y1, x2, y2)) / roi_area
        if coverage < 0.65:
            return False
    return True


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


def _same_large_scene_object(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
    *,
    frame_area: float,
    min_large_area_ratio: float,
) -> bool:
    first_area = _box_area(first)
    second_area = _box_area(second)
    if first_area <= 0 or second_area <= 0:
        return False
    larger = first if first_area >= second_area else second
    smaller = second if first_area >= second_area else first
    larger_area = max(first_area, second_area)
    smaller_area = min(first_area, second_area)
    if larger_area / max(frame_area, 1.0) < min_large_area_ratio:
        return False
    lx1, ly1, lx2, ly2 = larger
    sx1, sy1, sx2, sy2 = smaller
    large_w = max(1, lx2 - lx1)
    large_h = max(1, ly2 - ly1)
    expand_x = max(12, round(large_w * 0.08))
    expand_y = max(12, round(large_h * 0.08))
    small_cx = (sx1 + sx2) / 2.0
    small_cy = (sy1 + sy2) / 2.0
    center_inside = (
        lx1 - expand_x <= small_cx <= lx2 + expand_x
        and ly1 - expand_y <= small_cy <= ly2 + expand_y
    )
    if not center_inside:
        return False
    intersection = _intersection_area(first, second)
    smaller_coverage = intersection / max(smaller_area, 1)
    union_area = first_area + second_area - intersection
    contained_union = union_area / max(larger_area, 1) <= 1.35
    substantial_overlap = smaller_coverage >= 0.28 and smaller_area / max(larger_area, 1) <= 0.85
    return contained_union or substantial_overlap


def _same_large_bottle_edge_fragment(
    first: Detection,
    second: Detection,
    *,
    frame_width: int,
) -> bool:
    """Fold a cap/neck false label at a close-up bottle's frame edge.

    Transparent PET bottles often yield a confident label on their printed body
    plus a smaller, unrelated label on the clear neck. The second label is only
    treated as a fragment when it hugs a frame edge, is much smaller, and stays
    aligned with a bottle-sized primary box. Separate objects are still caught
    by the foreground multi-object gate later in the pipeline.
    """
    first_area = _box_area(first.xyxy)
    second_area = _box_area(second.xyxy)
    if first_area <= 0 or second_area <= 0:
        return False
    primary, fragment = (first, second) if first_area >= second_area else (second, first)
    if primary.cls_name not in BOTTLE_LIKE_CLASSES or primary.conf < fragment.conf:
        return False

    primary_area = max(first_area, second_area)
    fragment_area = min(first_area, second_area)
    if fragment_area / primary_area > 0.22:
        return False

    px1, py1, px2, py2 = primary.xyxy
    fx1, fy1, fx2, fy2 = fragment.xyxy
    primary_width = max(1, px2 - px1)
    primary_height = max(1, py2 - py1)
    fragment_height = max(1, fy2 - fy1)
    union_width = max(px2, fx2) - min(px1, fx1)
    union_height = max(py2, fy2) - min(py1, fy1)
    if union_width <= union_height or union_width < frame_width * 0.55:
        return False

    edge_margin = max(6, round(frame_width * 0.01))
    at_horizontal_edge = fx1 <= edge_margin or fx2 >= frame_width - edge_margin
    vertical_overlap = max(0, min(py2, fy2) - max(py1, fy1))
    aligned = vertical_overlap / fragment_height >= 0.65
    gap_x = max(px1 - fx2, fx1 - px2, 0)
    close_enough = gap_x <= max(80, round(primary_width * 0.82))
    compact_fragment = fragment_height <= primary_height * 0.72
    return at_horizontal_edge and aligned and close_enough and compact_fragment


def _collapse_single_object_scene_cluster(
    cluster: list[Detection],
    *,
    frame_width: int,
) -> Detection:
    for primary in sorted(cluster, key=_box_area_from_detection, reverse=True):
        edge_fragments = [
            item
            for item in cluster
            if item is not primary
            and _same_large_bottle_edge_fragment(
                primary,
                item,
                frame_width=frame_width,
            )
        ]
        if edge_fragments:
            return Detection(
                cls_id=primary.cls_id,
                cls_name=primary.cls_name,
                conf=primary.conf,
                xyxy=(
                    min(item.xyxy[0] for item in [primary, *edge_fragments]),
                    min(item.xyxy[1] for item in [primary, *edge_fragments]),
                    max(item.xyxy[2] for item in [primary, *edge_fragments]),
                    max(item.xyxy[3] for item in [primary, *edge_fragments]),
                ),
                source=primary.source,
                operator_label=primary.operator_label,
            )
    return _best_duplicate_candidate(cluster)


def _box_area_from_detection(detection: Detection) -> int:
    return _box_area(detection.xyxy)


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
    "collapse_single_object_scene_detections",
    "find_ambiguous_organic_candidate",
    "is_low_detail_empty_tray",
    "is_uniform_empty_tray_artifact",
    "is_verified_empty_tray",
    "merge_fragmented_same_label_detections",
    "suppress_overlapping_detections",
]
