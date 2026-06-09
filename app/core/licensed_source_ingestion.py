"""Licensed-source quality gates for manual training data."""

from __future__ import annotations

from app.core.training_source_flags import (
    is_camera_blur_augmented_meta,
    is_generated_meta,
    is_train_only_supplemental_meta,
)
from app.core.waste_categories import TRAINING_CLASS_ORDER_45, canonical_class_name

REFERENCE_MIN_REVIEWED = 6
STRONG_MIN_REVIEWED = 24
STRONG_MIN_HOLDOUT = 6
GENERATED_CAP_RATIO = 0.20

def validate_manual_url_source(
    *,
    class_name: str,
    source_url: str,
    source_page_url: str,
    source_license: str,
    source_author: str,
    source_type: str,
    generated: bool,
) -> dict[str, object]:
    canonical = canonical_class_name(class_name)
    if canonical not in TRAINING_CLASS_ORDER_45:
        raise ValueError(f"Class is outside the 45-class contract: {class_name}")
    missing = []
    if not source_url.strip():
        missing.append("source_url")
    if not source_page_url.strip():
        missing.append("source_page_url")
    if not source_license.strip():
        missing.append("source_license")
    if not source_author.strip():
        missing.append("source_author")
    if missing:
        raise ValueError("Web image import requires " + ", ".join(missing))
    clean_type = source_type.strip() or ("generated" if generated else "licensed_url")
    is_generated = generated or clean_type == "generated"
    return {
        "source_type": clean_type,
        "source_license": source_license.strip(),
        "license": source_license.strip(),
        "source_author": source_author.strip(),
        "canonical_class": canonical,
        "generated": bool(is_generated),
        "recognition_enabled": not is_generated,
        "split": "train" if is_generated else "",
        "split_lock": bool(is_generated),
    }


def source_manifest_issues(meta: dict) -> list[str]:
    source = str(meta.get("source") or "")
    generated = is_generated_meta(meta)
    augmented = is_camera_blur_augmented_meta(meta)
    if augmented:
        augmented_issues: list[str] = []
        if not str(meta.get("augmentation_parent") or "").strip():
            augmented_issues.append("missing_augmentation_parent")
        if not str(meta.get("augmentation_profile") or "").strip():
            augmented_issues.append("missing_augmentation_profile")
        if not str(meta.get("canonical_class") or "").strip():
            augmented_issues.append("missing_canonical_class")
        if str(meta.get("split") or "train").lower() != "train":
            augmented_issues.append("augmented_not_train_split")
        if meta.get("recognition_enabled", False):
            augmented_issues.append("augmented_reference_enabled")
        return augmented_issues
    web_like = source == "manual_web_import" or generated
    if not web_like:
        return []
    issues: list[str] = []
    required = {
        "source_url": meta.get("source_url"),
        "source_license": meta.get("source_license") or meta.get("license"),
        "source_author": meta.get("source_author"),
        "source_type": meta.get("source_type"),
        "canonical_class": meta.get("canonical_class"),
    }
    for key, value in required.items():
        if not str(value or "").strip():
            issues.append(f"missing_{key}")
    canonical = canonical_class_name(str(meta.get("canonical_class") or ""))
    if canonical and canonical not in TRAINING_CLASS_ORDER_45:
        issues.append("unknown_canonical_class")
    if is_train_only_supplemental_meta(meta) and str(meta.get("split") or "train").lower() != "train":
        issues.append("supplemental_not_train_split")
    if is_train_only_supplemental_meta(meta) and meta.get("recognition_enabled", False):
        issues.append("supplemental_reference_enabled")
    return issues
