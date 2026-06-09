"""Source quality reporting for manual and licensed training data."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageStat

from app.core.dataset_queue import is_trainable_meta
from app.core.licensed_source_ingestion import (
    GENERATED_CAP_RATIO,
    REFERENCE_MIN_REVIEWED,
    STRONG_MIN_HOLDOUT,
    STRONG_MIN_REVIEWED,
    source_manifest_issues,
)
from app.core.training_source_flags import is_camera_blur_augmented_meta, is_generated_meta
from app.core.vietnam_waste_targets import VIETNAM_TARGET_CLASSES, priority_for_class
from app.core.waste_categories import TRAINING_CLASS_ORDER_45, canonical_class_name

BLUR_VARIANCE_MIN = 18.0


def build_source_quality_report(queue_dir: Path) -> dict[str, object]:
    allowed = set(TRAINING_CLASS_ORDER_45)
    class_stats: dict[str, Counter[str]] = defaultdict(Counter)
    sources: Counter[str] = Counter()
    issues: list[dict[str, object]] = []
    image_hashes: Counter[str] = Counter()
    duplicate_images = 0
    blurry_images = 0
    total_images = 0
    for image_path in sorted(queue_dir.glob("*.jpg")) if queue_dir.exists() else []:
        total_images += 1
        meta = _read_meta(image_path.with_suffix(".json"))
        sources[str(meta.get("source") or "unknown")] += 1
        duplicate_images += _duplicate_increment(image_path, image_hashes)
        blur_score = _blur_score(image_path)
        if blur_score is not None and blur_score < BLUR_VARIANCE_MIN:
            blurry_images += 1
            issues.append({"image": str(image_path), "reason": "blurry_image", "score": blur_score})
        item_issues = source_manifest_issues(meta)
        for reason in item_issues:
            issues.append({"image": str(image_path), "reason": reason})
        _count_classes(meta, allowed, class_stats, item_issues)
    rows = [_class_report_row(name, class_stats[name]) for name in VIETNAM_TARGET_CLASSES]
    return {
        "queue_dir": str(queue_dir.resolve()),
        "total_images": total_images,
        "manual_web_images": sources.get("manual_web_import", 0),
        "generated_images": sum(row["generated"] for row in class_stats.values()),
        "augmented_images": sum(row["augmented"] for row in class_stats.values()),
        "invalid_source_images": len({issue["image"] for issue in issues if issue["reason"] != "blurry_image"}),
        "duplicate_images": duplicate_images,
        "blurry_images": blurry_images,
        "sources": dict(sources),
        "classes": rows,
        "issues": issues[:100],
    }


def _count_classes(
    meta: dict,
    allowed: set[str],
    class_stats: dict[str, Counter[str]],
    item_issues: list[str],
) -> None:
    trainable = is_trainable_meta(meta)
    reviewed = meta.get("reviewed") is True
    holdout = meta.get("holdout") is True or str(meta.get("split") or "").lower() == "test"
    for class_name in _classes_from_meta(meta, allowed):
        row = class_stats[class_name]
        row["images"] += 1
        row["reviewed"] += int(reviewed)
        row["holdout"] += int(reviewed and holdout)
        row["trainable"] += int(trainable)
        row["generated"] += int(is_generated_meta(meta))
        row["augmented"] += int(is_camera_blur_augmented_meta(meta))
        row["source_issues"] += len(item_issues)


def _class_report_row(class_name: str, counts: Counter[str]) -> dict[str, object]:
    reviewed = int(counts["reviewed"])
    holdout = int(counts["holdout"])
    generated = int(counts["generated"])
    generated_cap = max(0, int(max(1, reviewed) * GENERATED_CAP_RATIO))
    return {
        "class_name": class_name,
        "priority": priority_for_class(class_name),
        "images": int(counts["images"]),
        "trainable_count": int(counts["trainable"]),
        "reviewed_count": reviewed,
        "holdout_count": holdout,
        "generated_count": generated,
        "augmented_count": int(counts["augmented"]),
        "generated_cap": generated_cap,
        "generated_over_cap": generated > generated_cap,
        "source_issue_count": int(counts["source_issues"]),
        "missing_for_reference": max(0, REFERENCE_MIN_REVIEWED - reviewed),
        "missing_for_strong_train": max(0, STRONG_MIN_REVIEWED - reviewed),
        "missing_holdout_for_strong": max(0, STRONG_MIN_HOLDOUT - holdout),
    }


def _classes_from_meta(meta: dict, allowed: set[str]) -> set[str]:
    classes: set[str] = set()
    for box in meta.get("boxes") or []:
        if isinstance(box, dict):
            class_name = canonical_class_name(str(box.get("cls_name") or ""))
            if class_name in allowed:
                classes.add(class_name)
    return classes


def _duplicate_increment(path: Path, image_hashes: Counter[str]) -> int:
    digest = _sha1_file(path)
    if not digest:
        return 0
    image_hashes[digest] += 1
    return int(image_hashes[digest] > 1)


def _read_meta(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha1_file(path: Path) -> str:
    try:
        return hashlib.sha1(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _blur_score(path: Path) -> float | None:
    try:
        with Image.open(path) as image:
            return float(ImageStat.Stat(image.convert("L")).var[0])
    except OSError:
        return None
