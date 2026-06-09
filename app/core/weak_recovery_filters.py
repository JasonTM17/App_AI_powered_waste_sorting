"""Strict gates for weak-class recovery data and training decisions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from app.core.dataset_queue import REVIEW_REQUIRED_SOURCES, is_trainable_meta
from app.core.downloaded_zip_intake import (
    DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE,
    has_downloaded_bootstrap_source_metadata,
)
from app.core.training_source_flags import is_generated_meta
from app.core.waste_categories import canonical_class_name

WHOLE_IMAGE_COVERAGE_THRESHOLD = 0.92
WEAK_TARGET_BOX_COUNTS = {
    "Pen": 40,
    "Disposable tableware": 80,
    "Ceramic": 60,
    "Unknown plastic": 120,
    "Electronics": 60,
}
STABILITY_CLASSES = ("Battery", "Toothbrush", "Textile")
REQUIRED_IMPROVEMENT_CLASSES = ("Pen", "Disposable tableware", "Ceramic")
PHASE15_FOCUS_CLASSES = tuple(dict.fromkeys((*WEAK_TARGET_BOX_COUNTS, *STABILITY_CLASSES)))


def has_complete_web_license(meta: dict[str, Any]) -> bool:
    source = str(meta.get("source") or "")
    if source == DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE:
        return has_downloaded_bootstrap_source_metadata(meta)
    if source != "manual_web_import":
        return True
    required = (
        meta.get("source_url"),
        meta.get("source_page_url"),
        meta.get("source_license") or meta.get("license"),
        meta.get("source_author"),
        meta.get("source_type"),
        meta.get("canonical_class"),
    )
    return all(str(value or "").strip() for value in required)


def allows_full_image_bbox(meta: dict[str, Any]) -> bool:
    return bool(
        meta.get("whole_image_allowed")
        or meta.get("whole_image_ok")
        or meta.get("single_object_product_photo")
    )


def bbox_coverages(meta: dict[str, Any], image_path: Path) -> list[tuple[str, float]]:
    width, height = _image_size(image_path)
    image_area = max(1.0, float(width * height))
    values: list[tuple[str, float]] = []
    for box in meta.get("boxes") or []:
        if not isinstance(box, dict):
            continue
        xyxy = box.get("xyxy") or []
        if len(xyxy) < 4:
            continue
        x1, y1, x2, y2 = (float(value) for value in xyxy[:4])
        bw = max(0.0, min(float(width), x2) - max(0.0, x1))
        bh = max(0.0, min(float(height), y2) - max(0.0, y1))
        values.append((canonical_class_name(str(box.get("cls_name") or "")), (bw * bh) / image_area))
    return values


def max_bbox_coverage(meta: dict[str, Any], image_path: Path) -> float:
    return max((coverage for _name, coverage in bbox_coverages(meta, image_path)), default=0.0)


def has_full_image_bbox(
    meta: dict[str, Any],
    image_path: Path,
    *,
    threshold: float = WHOLE_IMAGE_COVERAGE_THRESHOLD,
) -> bool:
    return max_bbox_coverage(meta, image_path) >= threshold


def strict_recovery_allowed(
    meta: dict[str, Any],
    image_path: Path,
    *,
    threshold: float = WHOLE_IMAGE_COVERAGE_THRESHOLD,
) -> tuple[bool, str]:
    if not is_trainable_meta(meta):
        return False, "not_trainable"
    if meta.get("needs_annotation") is True:
        return False, "needs_annotation"
    if is_generated_meta(meta):
        return False, "generated"
    source = str(meta.get("source") or "")
    if source in REVIEW_REQUIRED_SOURCES and meta.get("reviewed") is not True:
        return False, "not_reviewed"
    if not has_complete_web_license(meta):
        return False, "missing_web_license"
    if has_full_image_bbox(meta, image_path, threshold=threshold) and not allows_full_image_bbox(meta):
        return False, "whole_image_bbox"
    return True, ""


def target_classes_from_meta(meta: dict[str, Any]) -> set[str]:
    classes = set()
    for box in meta.get("boxes") or []:
        if isinstance(box, dict):
            class_name = canonical_class_name(str(box.get("cls_name") or ""))
            if class_name in PHASE15_FOCUS_CLASSES:
                classes.add(class_name)
    return classes


def _image_size(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            return image.size
    except OSError:
        return (1, 1)


__all__ = [
    "PHASE15_FOCUS_CLASSES",
    "REQUIRED_IMPROVEMENT_CLASSES",
    "STABILITY_CLASSES",
    "WEAK_TARGET_BOX_COUNTS",
    "WHOLE_IMAGE_COVERAGE_THRESHOLD",
    "allows_full_image_bbox",
    "bbox_coverages",
    "has_complete_web_license",
    "has_full_image_bbox",
    "max_bbox_coverage",
    "strict_recovery_allowed",
    "target_classes_from_meta",
]
