"""Small image heuristics for real-camera classes the detector confuses often."""

from __future__ import annotations

from dataclasses import replace

import cv2
import numpy as np

from app.core.events import Detection
from app.core.waste_categories import default_class_id_for_name

UNKNOWN_OBJECT_CLASS_ID = -401
LEAFY_ORGANIC_CORRECTABLE_CLASSES = {
    "Aluminum can",
    "Cardboard",
    "Paper",
    "Paper bag",
    "Plastic bag",
    "Plastic bottle",
    "Plastic cup",
    "Textile",
    "Wood",
}


def apply_visual_post_corrections(
    frame_bgr: np.ndarray,
    detections: list[Detection],
    *,
    unknown_class_name: str = "Unknown object",
) -> list[Detection]:
    """Correct high-value real-camera mistakes without overriding strong YOLO labels."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] < 3 or not detections:
        return detections

    out: list[Detection] = []
    for detection in detections:
        if detection.source == "foreground_multi_object":
            out.append(detection)
            continue
        corrected = detection
        if _can_correct_leafy_organic(detection, unknown_class_name) and _looks_like_leafy_organic(
            frame_bgr, detection.xyxy
        ):
            corrected = _replace_detection(
                detection,
                "Organic",
                source="visual_correction:leafy_organic",
                operator_label="La cay",
            )
        elif detection.cls_name == "Organic" and detection.conf <= 0.68:
            if _looks_like_elongated_wooden_utensil(frame_bgr, detection.xyxy):
                corrected = _replace_detection(
                    detection,
                    "Wood",
                    source="visual_correction:wooden_utensil",
                    operator_label="Thia go",
                )
        elif detection.cls_name == "Aluminum can" and detection.conf <= 0.62:
            if _looks_like_transparent_plastic_bottle(frame_bgr, detection.xyxy):
                corrected = _replace_detection(
                    detection,
                    "Plastic bottle",
                    source="visual_correction:plastic_bottle",
                    operator_label="Chai nhua PET",
                )
        elif detection.cls_name == "Plastic bottle":
            if _looks_like_pen_like_tool(frame_bgr, detection.xyxy):
                corrected = _replace_detection(
                    detection,
                    "Pen",
                    source="visual_correction:pen",
                    operator_label="But bi",
                )
        elif detection.cls_name == "Glass bottle" and detection.conf < 0.45:
            corrected = _replace_detection(
                detection,
                unknown_class_name,
                cls_id=UNKNOWN_OBJECT_CLASS_ID,
                source="visual_correction:low_conf_glass",
            )
        elif detection.cls_name == "Paper" and detection.conf <= 0.35:
            if _looks_like_metal_utensil(frame_bgr, detection.xyxy):
                corrected = _replace_detection(
                    detection,
                    "Iron utensils",
                    source="visual_correction:metal_utensil",
                    operator_label="Muong kim loai",
                )
        elif detection.cls_name == unknown_class_name:
            if _looks_like_battery(frame_bgr, detection.xyxy):
                corrected = _replace_detection(
                    detection,
                    "Battery",
                    source="visual_correction:battery",
                    operator_label="Pin AA/AAA",
                )
            elif _looks_like_pen_like_tool(frame_bgr, detection.xyxy):
                corrected = _replace_detection(
                    detection,
                    "Pen",
                    source="visual_correction:pen",
                    operator_label="But bi",
                )
            elif _looks_like_metal_utensil(frame_bgr, detection.xyxy):
                corrected = _replace_detection(
                    detection,
                    "Iron utensils",
                    source="visual_correction:metal_utensil",
                    operator_label="Muong kim loai",
                )
            elif _looks_like_eggshell(frame_bgr, detection.xyxy):
                corrected = _replace_detection(
                    detection,
                    "Eggshell",
                    cls_id=UNKNOWN_OBJECT_CLASS_ID - 1,
                    source="visual_correction:eggshell",
                )
            elif detection.conf >= 0.70 and _looks_like_unknown_transparent_plastic_bottle(
                frame_bgr,
                detection.xyxy,
            ):
                corrected = _replace_detection(
                    detection,
                    "Plastic bottle",
                    source="visual_correction:plastic_bottle",
                    operator_label="Chai nhua PET",
                )
            elif detection.conf >= 0.35 and _looks_like_ceramic_dish(frame_bgr, detection.xyxy):
                corrected = _replace_detection(
                    detection,
                    "Ceramic",
                    source="visual_correction:ceramic_dish",
                    operator_label="Gom su",
                )
            elif detection.conf >= 0.35:
                crumpled_paper_box = _crumpled_paper_box(frame_bgr, detection.xyxy)
                if crumpled_paper_box is not None:
                    corrected = _replace_detection(
                        detection,
                        "Paper",
                        source="visual_correction:crumpled_paper",
                        operator_label="Giay vo",
                        xyxy=crumpled_paper_box,
                    )
        out.append(corrected)
    return out


def _can_correct_leafy_organic(detection: Detection, unknown_class_name: str) -> bool:
    if detection.cls_name == "Organic":
        return True
    if detection.cls_name == unknown_class_name:
        return True
    return detection.conf <= 0.62 and detection.cls_name in LEAFY_ORGANIC_CORRECTABLE_CLASSES


def _replace_detection(
    detection: Detection,
    cls_name: str,
    *,
    cls_id: int | None = None,
    source: str,
    operator_label: str = "",
    xyxy: tuple[int, int, int, int] | None = None,
) -> Detection:
    resolved_cls_id = default_class_id_for_name(cls_name)
    return replace(
        detection,
        cls_id=cls_id if cls_id is not None else (resolved_cls_id or detection.cls_id),
        cls_name=cls_name,
        source=source,
        operator_label=operator_label,
        xyxy=xyxy if xyxy is not None else detection.xyxy,
    )


def _looks_like_elongated_wooden_utensil(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> bool:
    crop = _crop(frame_bgr, xyxy, pad_ratio=0.03)
    if crop is None:
        return False
    mask = _foreground_mask(crop)
    stats = _mask_stats(crop, mask)
    if stats is None:
        return False

    return (
        stats["area_ratio"] >= 0.08
        and stats["extent"] >= 0.18
        and stats["oriented_aspect"] >= 2.25
        and 95.0 <= stats["value_mean"] <= 235.0
        and 5.0 <= stats["saturation_mean"] <= 95.0
        and stats["warmth"] >= 7.0
    )


def _looks_like_metal_utensil(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> bool:
    crop = _crop(frame_bgr, xyxy, pad_ratio=0.02)
    if crop is None:
        return False

    box_w = max(1, int(xyxy[2]) - int(xyxy[0]))
    box_h = max(1, int(xyxy[3]) - int(xyxy[1]))
    box_aspect = box_w / float(box_h)
    if not (box_aspect >= 1.20 or box_aspect <= 0.83):
        return False

    mask = _foreground_mask(crop)
    stats = _mask_stats(crop, mask)
    if stats is None:
        return False

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    low_saturation_ratio = float(np.mean(saturation < 58))
    colored_ratio = float(np.mean(saturation > 90))
    strong_colored_ratio = float(np.mean((saturation > 105) & (value > 60)))
    glare_ratio = float(np.mean((saturation < 42) & (value > 205)))
    dark_metal_ratio = float(np.mean((saturation < 70) & (value < 115)))
    contrast = float(np.std(gray))
    width_variation, max_to_median_width = _silhouette_width_variation(
        mask, horizontal=box_aspect >= 1.0
    )

    standard_utensil = (
        stats["area_ratio"] >= 0.055
        and stats["extent"] >= 0.08
        and stats["oriented_aspect"] >= 2.05
        and stats["saturation_mean"] <= 58.0
        and abs(stats["warmth"]) <= 24.0
        and low_saturation_ratio >= 0.60
        and colored_ratio <= 0.10
        and strong_colored_ratio <= 0.045
        and width_variation >= 0.36
        and max_to_median_width >= 1.35
        and (glare_ratio >= 0.004 or (dark_metal_ratio >= 0.05 and width_variation >= 0.50))
        and contrast >= 16.0
        and stats["edge_ratio"] >= 0.0025
    )
    close_up_spoon = (
        box_aspect >= 1.20
        and stats["area_ratio"] >= 0.45
        and stats["extent"] >= 0.40
        and stats["oriented_aspect"] >= 1.25
        and stats["circularity"] <= 0.42
        and stats["saturation_mean"] <= 24.0
        and abs(stats["warmth"]) <= 18.0
        and low_saturation_ratio >= 0.72
        and colored_ratio <= 0.08
        and strong_colored_ratio <= 0.035
        and width_variation >= 0.42
        and max_to_median_width >= 1.20
        and glare_ratio >= 0.002
        and dark_metal_ratio >= 0.035
        and contrast >= 12.0
        and stats["edge_ratio"] >= 0.0025
    )
    return standard_utensil or close_up_spoon


def _looks_like_pen_like_tool(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> bool:
    crop = _crop(frame_bgr, xyxy, pad_ratio=0.015)
    if crop is None:
        return False

    box_w = max(1, int(xyxy[2]) - int(xyxy[0]))
    box_h = max(1, int(xyxy[3]) - int(xyxy[1]))
    box_aspect = box_w / float(box_h)
    if not (box_aspect >= 3.1 or box_aspect <= 0.32):
        return False

    if _looks_like_unknown_transparent_plastic_bottle(frame_bgr, xyxy):
        return False

    mask = _foreground_mask(crop)
    stats = _mask_stats(crop, mask)
    if stats is None:
        return False

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    blue_ratio = float(np.mean((hsv[:, :, 0] >= 88) & (hsv[:, :, 0] <= 135) & (saturation > 45)))
    dark_ratio = float(np.mean(value < 120))
    low_saturation_ratio = float(np.mean(saturation < 80))
    width_variation, max_to_median_width = _silhouette_width_variation(
        mask,
        horizontal=box_aspect >= 1.0,
    )

    return (
        stats["area_ratio"] >= 0.035
        and stats["extent"] >= 0.08
        and stats["oriented_aspect"] >= 3.0
        and stats["circularity"] <= 0.38
        and stats["edge_ratio"] >= 0.0015
        and max_to_median_width <= 2.80
        and width_variation <= 0.78
        and (blue_ratio >= 0.015 or dark_ratio >= 0.08 or low_saturation_ratio >= 0.55)
    )


def _looks_like_battery(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> bool:
    crop = _crop(frame_bgr, xyxy, pad_ratio=0.02)
    if crop is None:
        return False

    box_w = max(1, int(xyxy[2]) - int(xyxy[0]))
    box_h = max(1, int(xyxy[3]) - int(xyxy[1]))
    box_aspect = box_w / float(box_h)
    horizontal = box_aspect >= 1.0
    if not (box_aspect >= 1.55 or box_aspect <= 0.65):
        return False

    mask = _foreground_mask(crop)
    stats = _mask_stats(crop, mask)
    if stats is None:
        return False

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    object_mask = mask > 0
    if not np.any(object_mask):
        return False

    warm_metal = (
        (hue >= 5)
        & (hue <= 34)
        & (saturation >= 32)
        & (value >= 72)
        & (value <= 235)
    )
    dark_body = value <= 118
    neutral_dark_body = dark_body & (saturation <= 135)
    bright_print = (value >= 145) & (saturation <= 105)

    axis_length = crop.shape[1] if horizontal else crop.shape[0]
    if axis_length < 24:
        return False
    first_slice = slice(0, max(1, axis_length // 3))
    last_slice = slice(max(0, axis_length * 2 // 3), axis_length)

    if horizontal:
        first_mask = object_mask[:, first_slice]
        last_mask = object_mask[:, last_slice]
        first_warm = warm_metal[:, first_slice]
        last_warm = warm_metal[:, last_slice]
        first_dark = neutral_dark_body[:, first_slice]
        last_dark = neutral_dark_body[:, last_slice]
    else:
        first_mask = object_mask[first_slice, :]
        last_mask = object_mask[last_slice, :]
        first_warm = warm_metal[first_slice, :]
        last_warm = warm_metal[last_slice, :]
        first_dark = neutral_dark_body[first_slice, :]
        last_dark = neutral_dark_body[last_slice, :]

    def _ratio(region: np.ndarray, region_mask: np.ndarray) -> float:
        active = region_mask > 0
        if not np.any(active):
            return 0.0
        return float(np.mean(region[active]))

    warm_at_one_end = max(
        _ratio(first_warm, first_mask),
        _ratio(last_warm, last_mask),
    )
    dark_at_other_end = max(
        _ratio(first_dark, first_mask),
        _ratio(last_dark, last_mask),
    )
    object_warm_ratio = float(np.mean(warm_metal[object_mask]))
    object_dark_ratio = float(np.mean(neutral_dark_body[object_mask]))
    object_print_ratio = float(np.mean(bright_print[object_mask]))
    width_variation, max_to_median_width = _silhouette_width_variation(
        mask,
        horizontal=horizontal,
    )
    contrast = float(np.std(gray))

    return (
        stats["area_ratio"] >= 0.15
        and stats["extent"] >= 0.24
        and stats["oriented_aspect"] >= 2.05
        and stats["circularity"] <= 0.58
        and warm_at_one_end >= 0.18
        and dark_at_other_end >= 0.25
        and object_warm_ratio >= 0.08
        and object_dark_ratio >= 0.22
        and object_print_ratio <= 0.30
        and width_variation <= 0.82
        and max_to_median_width <= 2.35
        and contrast >= 18.0
    )


def _looks_like_leafy_organic(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> bool:
    crop = _crop(frame_bgr, xyxy, pad_ratio=0.02)
    if crop is None:
        return False

    box_w = max(1, int(xyxy[2]) - int(xyxy[0]))
    box_h = max(1, int(xyxy[3]) - int(xyxy[1]))
    box_aspect = box_w / float(box_h)

    mask = _foreground_mask(crop)
    stats = _mask_stats(crop, mask)
    if stats is None:
        return False

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    green_pixels = (
        (hue >= 28)
        & (hue <= 98)
        & (saturation > 22)
        & (value > 22)
        & (value < 238)
    )
    red_or_blue_pixels = (
        ((hue <= 14) | (hue >= 164) | ((hue >= 100) & (hue <= 132)))
        & (saturation > 68)
        & (value > 50)
    )
    object_mask = mask > 0
    if not np.any(object_mask):
        return False

    object_pixels = crop[object_mask]
    mean_bgr = object_pixels.mean(axis=0)
    green_dominance = float(mean_bgr[1] - max(mean_bgr[0], mean_bgr[2]))
    green_frame_ratio = float(np.mean(green_pixels))
    green_object_ratio = float(np.mean(green_pixels[object_mask]))
    red_or_blue_ratio = float(np.mean(red_or_blue_pixels))
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 28, 90)
    edge_ratio = float(np.count_nonzero(edges)) / float(max(1, edges.size))

    return (
        stats["area_ratio"] >= 0.055
        and green_frame_ratio >= 0.055
        and green_object_ratio >= 0.28
        and green_dominance >= 8.0
        and red_or_blue_ratio <= 0.16
        and stats["saturation_mean"] >= 20.0
        and stats["edge_ratio"] >= 0.0025
        and edge_ratio >= 0.006
        and (
            stats["oriented_aspect"] >= 1.35
            or box_aspect >= 1.25
            or box_aspect <= 0.80
        )
    )


def _silhouette_width_variation(mask: np.ndarray, *, horizontal: bool) -> tuple[float, float]:
    """Return how much the object width changes along its long axis."""
    if mask.size == 0:
        return 0.0, 0.0
    axis = 1 if horizontal else 0
    counts = np.count_nonzero(mask > 0, axis=axis)
    active = counts[counts > 0]
    if active.size < 3:
        return 0.0, 0.0
    p90 = float(np.percentile(active, 90))
    p10 = float(np.percentile(active, 10))
    median = float(np.median(active))
    variation = (p90 - p10) / max(p90, 1.0)
    max_to_median = float(np.max(active)) / max(median, 1.0)
    return variation, max_to_median


def _looks_like_eggshell(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> bool:
    crop = _crop(frame_bgr, xyxy, pad_ratio=0.08)
    if crop is None:
        return False
    mask = _foreground_mask(crop)
    stats = _mask_stats(crop, mask)
    if stats is None:
        return False

    return (
        0.12 <= stats["area_ratio"] <= 0.82
        and 0.58 <= stats["box_aspect"] <= 1.55
        and stats["oriented_aspect"] <= 1.75
        and stats["circularity"] >= 0.38
        and 105.0 <= stats["value_mean"] <= 238.0
        and 3.0 <= stats["saturation_mean"] <= 85.0
        and stats["warmth"] >= 4.0
    )


def _looks_like_ceramic_dish(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> bool:
    crop = _crop(frame_bgr, xyxy, pad_ratio=0.04)
    if crop is None:
        return False
    mask = _foreground_mask(crop)
    stats = _mask_stats(crop, mask)
    if stats is None:
        return False

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    saturation_ratio = float(np.mean(hsv[:, :, 1] > 35))
    bright_ratio = float(np.mean(hsv[:, :, 2] > 170))
    return (
        stats["area_ratio"] >= 0.20
        and 0.45 <= stats["box_aspect"] <= 2.40
        and saturation_ratio >= 0.08
        and bright_ratio >= 0.20
        and stats["edge_ratio"] >= 0.006
    )


def _looks_like_transparent_plastic_bottle(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> bool:
    crop = _crop(frame_bgr, xyxy, pad_ratio=0.02)
    if crop is None:
        return False

    box_w = max(1, int(xyxy[2]) - int(xyxy[0]))
    box_h = max(1, int(xyxy[3]) - int(xyxy[1]))
    box_aspect = box_w / float(box_h)
    if not 0.35 <= box_aspect <= 4.80:
        return False

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 24, 80)

    neutral_bright_ratio = float(np.mean((saturation < 58) & (value > 145)))
    glare_ratio = float(np.mean((saturation < 45) & (value > 212)))
    colored_label_ratio = float(np.mean((saturation > 68) & (value > 58)))
    red_or_blue_label_ratio = float(
        np.mean(
            ((hue <= 12) | (hue >= 165) | ((hue >= 94) & (hue <= 130)))
            & (saturation > 62)
            & (value > 55)
        )
    )
    dark_print_ratio = float(np.mean((value < 125) & (saturation > 35)))
    edge_ratio = float(np.count_nonzero(edges)) / float(max(1, edges.size))
    contrast = float(np.std(gray))
    saturation_mean = float(np.mean(saturation))

    return (
        neutral_bright_ratio >= 0.24
        and glare_ratio >= 0.006
        and colored_label_ratio >= 0.025
        and colored_label_ratio <= 0.38
        and red_or_blue_label_ratio >= 0.010
        and dark_print_ratio <= 0.38
        and edge_ratio >= 0.004
        and contrast >= 12.0
        and saturation_mean <= 85.0
    )


def _looks_like_unknown_transparent_plastic_bottle(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> bool:
    box_w = max(1, int(xyxy[2]) - int(xyxy[0]))
    box_h = max(1, int(xyxy[3]) - int(xyxy[1]))
    box_aspect = box_w / float(box_h)
    return 0.42 <= box_aspect <= 2.75 and _looks_like_transparent_plastic_bottle(frame_bgr, xyxy)


def _looks_like_crumpled_paper(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> bool:
    crop = _crop(frame_bgr, xyxy, pad_ratio=0.03)
    if crop is None:
        return False

    box_w = max(1, int(xyxy[2]) - int(xyxy[0]))
    box_h = max(1, int(xyxy[3]) - int(xyxy[1]))
    box_aspect = box_w / float(box_h)
    if not 0.45 <= box_aspect <= 2.80:
        return False

    mask = _foreground_mask(crop)
    stats = _mask_stats(crop, mask)
    if stats is not None and stats["oriented_aspect"] >= 3.70 and stats["extent"] >= 0.18:
        return False

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 35, 105)

    neutral_bright_ratio = float(np.mean((saturation < 55) & (value > 145)))
    colored_ratio = float(np.mean(saturation > 70))
    dark_ink_ratio = float(np.mean((value < 125) & (saturation < 95)))
    shadow_ratio = float(np.mean(gray < max(25.0, float(np.mean(gray)) - 24.0)))
    edge_ratio = float(np.count_nonzero(edges)) / float(max(1, edges.size))
    contrast = float(np.std(gray))
    return (
        neutral_bright_ratio >= 0.42
        and colored_ratio <= 0.20
        and 0.035 <= dark_ink_ratio <= 0.28
        and shadow_ratio <= 0.30
        and edge_ratio >= 0.005
        and contrast >= 13.0
        and 105.0 <= float(np.mean(value)) <= 240.0
    )


def _crumpled_paper_box(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> tuple[int, int, int, int] | None:
    if _looks_like_crumpled_paper(frame_bgr, xyxy):
        return xyxy
    expanded = _expanded_neutral_fragment_box(frame_bgr, xyxy)
    if expanded is None:
        return None
    return expanded if _looks_like_crumpled_paper(frame_bgr, expanded) else None


def _expanded_neutral_fragment_box(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> tuple[int, int, int, int] | None:
    height, width = frame_bgr.shape[:2]
    if height <= 0 or width <= 0:
        return None
    x1, y1, x2, y2 = xyxy
    seed_w = max(1, int(x2) - int(x1))
    seed_h = max(1, int(y2) - int(y1))
    search_pad = max(48, round(max(width, height) * 0.24), seed_w, seed_h)
    sx1 = max(0, int(x1) - search_pad)
    sy1 = max(0, int(y1) - search_pad)
    sx2 = min(width, int(x2) + search_pad)
    sy2 = min(height, int(y2) + search_pad)
    region = frame_bgr[sy1:sy2, sx1:sx2, :3]
    if region.size == 0:
        return None

    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 30, 95)
    local_mean = float(np.mean(gray))
    dark_folds = (value < max(142.0, local_mean - 18.0)) & (saturation < 100)
    neutral_edges = (edges > 0) & (saturation < 90)
    mask = np.where(dark_folds | neutral_edges, 255, 0).astype("uint8")
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.dilate(mask, kernel, iterations=1)

    seed_center_x = ((int(x1) + int(x2)) / 2.0) - sx1
    seed_center_y = ((int(y1) + int(y2)) / 2.0) - sy1
    contours, _hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[tuple[int, int, int, int]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 18.0:
            continue
        cx, cy, cw, ch = cv2.boundingRect(contour)
        center_x = cx + cw / 2.0
        center_y = cy + ch / 2.0
        near_seed = (
            abs(center_x - seed_center_x) <= search_pad
            and abs(center_y - seed_center_y) <= search_pad
        )
        intersects_seed = not (
            cx > seed_center_x + seed_w
            or cx + cw < seed_center_x - seed_w
            or cy > seed_center_y + seed_h
            or cy + ch < seed_center_y - seed_h
        )
        if near_seed or intersects_seed:
            boxes.append((cx, cy, cx + cw, cy + ch))
    if not boxes:
        return None

    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[2] for box in boxes)
    bottom = max(box[3] for box in boxes)
    box_w = max(1, right - left)
    box_h = max(1, bottom - top)
    pad_x = max(12, round(box_w * 0.28))
    pad_y = max(12, round(box_h * 0.28))
    out = (
        max(0, sx1 + left - pad_x),
        max(0, sy1 + top - pad_y),
        min(width, sx1 + right + pad_x),
        min(height, sy1 + bottom + pad_y),
    )
    out_area = max(1, (out[2] - out[0]) * (out[3] - out[1]))
    frame_area = max(1, width * height)
    if out_area / float(frame_area) < 0.04 or out_area / float(frame_area) > 0.82:
        return None
    aspect = (out[2] - out[0]) / float(max(1, out[3] - out[1]))
    return out if 0.42 <= aspect <= 2.90 else None


def _crop(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
    *,
    pad_ratio: float = 0.0,
) -> np.ndarray | None:
    height, width = frame_bgr.shape[:2]
    x1, y1, x2, y2 = xyxy
    box_w = max(1, int(x2) - int(x1))
    box_h = max(1, int(y2) - int(y1))
    pad_x = round(box_w * pad_ratio)
    pad_y = round(box_h * pad_ratio)
    x1 = max(0, int(x1) - pad_x)
    y1 = max(0, int(y1) - pad_y)
    x2 = min(width, int(x2) + pad_x)
    y2 = min(height, int(y2) + pad_y)
    if x2 <= x1 or y2 <= y1:
        return None
    crop = frame_bgr[y1:y2, x1:x2, :3]
    return crop if crop.size else None


def _foreground_mask(crop_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    border = np.concatenate(
        [
            gray[: max(1, gray.shape[0] // 10), :].reshape(-1),
            gray[-max(1, gray.shape[0] // 10) :, :].reshape(-1),
            gray[:, : max(1, gray.shape[1] // 10)].reshape(-1),
            gray[:, -max(1, gray.shape[1] // 10) :].reshape(-1),
        ]
    )
    background = float(np.median(border)) if border.size else float(np.median(gray))
    diff = cv2.absdiff(gray, np.full_like(gray, int(background)))
    mask = (diff > 14) | (hsv[:, :, 1] > 28)
    kernel = np.ones((5, 5), np.uint8)
    mask_u8 = mask.astype(np.uint8) * 255
    mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, kernel)
    mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel)
    return mask_u8


def _mask_stats(crop_bgr: np.ndarray, mask: np.ndarray) -> dict[str, float] | None:
    contours, _hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(contour))
    crop_area = float(max(1, crop_bgr.shape[0] * crop_bgr.shape[1]))
    if area < max(24.0, crop_area * 0.015):
        return None
    _x, _y, w, h = cv2.boundingRect(contour)
    rect = cv2.minAreaRect(contour)
    rect_w, rect_h = rect[1]
    short_side = max(1.0, min(float(rect_w), float(rect_h)))
    long_side = max(float(rect_w), float(rect_h), short_side)
    perimeter = float(cv2.arcLength(contour, True))
    circularity = (4.0 * np.pi * area / (perimeter * perimeter)) if perimeter > 0 else 0.0

    object_pixels = crop_bgr[mask > 0]
    if object_pixels.size == 0:
        return None
    hsv_pixels = cv2.cvtColor(object_pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    mean_bgr = object_pixels.mean(axis=0)
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 35, 110)

    return {
        "area_ratio": area / crop_area,
        "box_aspect": float(w) / float(max(1, h)),
        "oriented_aspect": long_side / short_side,
        "extent": area / float(max(1, w * h)),
        "circularity": float(circularity),
        "saturation_mean": float(np.mean(hsv_pixels[:, 1])),
        "value_mean": float(np.mean(hsv_pixels[:, 2])),
        "warmth": float(mean_bgr[2] - mean_bgr[0]),
        "edge_ratio": float(np.count_nonzero(edges)) / float(max(1, edges.size)),
    }


__all__ = ["apply_visual_post_corrections"]
