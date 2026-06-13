"""Learn-now readiness checks for manual reference recognition and fast training."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from app.core.common_waste_catalog import common_waste_class_names
from app.core.dataset_catalog import DatasetCatalog
from app.core.dataset_queue import is_trainable_meta, is_trusted_meta
from app.core.licensed_source_ingestion import (
    GENERATED_CAP_RATIO,
    STRONG_MIN_HOLDOUT,
    source_manifest_issues,
)
from app.core.manual_reference_recognition import MANUAL_REFERENCE_SOURCES
from app.core.training_source_flags import is_generated_meta, is_train_only_supplemental_meta
from app.core.vietnam_waste_targets import VIETNAM_TARGET_CLASSES, priority_for_class
from app.core.waste_categories import (
    TRAINING_CLASS_ORDER_45,
    canonical_class_name,
    category_for_class,
    default_class_id_for_name,
)

REFERENCE_MIN_REVIEWED = 6
MICRO_TRAIN_MIN_REVIEWED = 6
STRONG_TRAIN_MIN_REVIEWED = 24
STRONG_TRAIN_MIN_HOLDOUT = STRONG_MIN_HOLDOUT


def build_learn_now_status(queue_dir: Path, selected_class: str = "") -> dict[str, object]:
    """Return per-class readiness for immediate recognition and candidate training."""
    allowed = set(TRAINING_CLASS_ORDER_45)
    selected = canonical_class_name(selected_class)
    class_names = set(common_waste_class_names()) | set(VIETNAM_TARGET_CLASSES)
    if selected:
        class_names.add(selected)

    stats: dict[str, Counter[str]] = defaultdict(Counter)
    blocked_labels: Counter[str] = Counter()
    total_images = 0
    total_boxes = 0
    images = sorted(queue_dir.glob("*.jpg")) if queue_dir.exists() else []
    for image_path in images:
        try:
            meta = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(meta, dict):
            continue
        total_images += 1
        total_boxes += _accumulate_meta_stats(
            meta,
            allowed=allowed,
            class_names=class_names,
            stats=stats,
            blocked_labels=blocked_labels,
        )

    rows = [_status_row(class_name, stats[class_name]) for class_name in sorted(class_names)]
    selected_status = (
        _status_row(selected, stats[selected])
        if selected
        else (next((row for row in rows if row["class_name"] == "Pen"), rows[0] if rows else None))
    )
    return {
        "selected_class": selected,
        "selected": selected_status,
        "classes": rows,
        "blocked_labels": dict(blocked_labels.most_common(30)),
        "total_images": total_images,
        "total_boxes": total_boxes,
        "queue_dir": str(queue_dir.resolve()),
    }


def build_selected_learn_now_status(
    queue_dir: Path,
    selected_class: str,
    catalog_path: Path,
) -> dict[str, object]:
    """Build readiness by reading metadata only for the selected catalog class."""
    selected = canonical_class_name(selected_class)
    if not selected:
        return build_learn_now_status(queue_dir, selected_class)

    catalog = DatasetCatalog(catalog_path)
    try:
        rows, selected_total = catalog.list_items_for_box_class(selected, limit=None)
        catalog_total = catalog.count_total()
        total_boxes = catalog.count_boxes_total()
    finally:
        catalog.close()
    if catalog_total == 0 and queue_dir.exists() and any(queue_dir.glob("*.jpg")):
        return build_learn_now_status(queue_dir, selected)

    stats: dict[str, Counter[str]] = defaultdict(Counter)
    blocked_labels: Counter[str] = Counter()
    class_names = {selected}
    valid_images = 0
    for row in rows:
        image_path = Path(str(row.get("image_path") or ""))
        try:
            meta = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(meta, dict):
            continue
        valid_images += 1
        _accumulate_meta_stats(
            meta,
            allowed={selected},
            class_names=class_names,
            stats=stats,
            blocked_labels=blocked_labels,
            class_filter=selected,
        )

    selected_status = _status_row(selected, stats[selected])
    return {
        "selected_class": selected,
        "selected": selected_status,
        "classes": [selected_status],
        "blocked_labels": dict(blocked_labels.most_common(30)),
        "total_images": catalog_total,
        "selected_images_scanned": valid_images,
        "selected_images": selected_total,
        "total_boxes": total_boxes,
        "queue_dir": str(queue_dir.resolve()),
    }


def _accumulate_meta_stats(
    meta: dict[str, object],
    *,
    allowed: set[str],
    class_names: set[str],
    stats: dict[str, Counter[str]],
    blocked_labels: Counter[str],
    class_filter: str | None = None,
) -> int:
    source = str(meta.get("source") or "")
    trainable = is_trainable_meta(meta)
    reviewed = meta.get("reviewed") is True and meta.get("bbox_reviewed") is True
    holdout = meta.get("holdout") is True or str(meta.get("split") or "").lower() == "test"
    generated = is_generated_meta(meta)
    train_only_supplemental = is_train_only_supplemental_meta(meta)
    source_issue_count = len(source_manifest_issues(meta))
    eligible_reviewed = (
        reviewed
        and is_trusted_meta(meta)
        and meta.get("training_excluded") is not True
        and not train_only_supplemental
    )
    reference_allowed = (
        trainable
        and reviewed
        and not holdout
        and not train_only_supplemental
        and source in MANUAL_REFERENCE_SOURCES
        and bool(meta.get("recognition_enabled", True))
    )
    classes_in_item: set[str] = set()
    total_boxes = 0
    for box in meta.get("boxes") or []:
        if not isinstance(box, dict):
            continue
        total_boxes += 1
        raw_name = str(box.get("cls_name") or "").strip()
        class_name = canonical_class_name(raw_name)
        if class_name not in allowed:
            if raw_name and class_filter is None:
                blocked_labels[raw_name] += 1
            continue
        classes_in_item.add(class_name)
        class_names.add(class_name)
    if class_filter is not None:
        classes_in_item.intersection_update({class_filter})
    for class_name in classes_in_item:
        stats[class_name]["images"] += 1
        if trainable:
            stats[class_name]["trainable"] += 1
        if generated:
            stats[class_name]["generated"] += 1
        stats[class_name]["source_issues"] += source_issue_count
        if reviewed:
            stats[class_name]["reviewed"] += 1
        if reviewed and trainable:
            stats[class_name]["trainable_reviewed"] += 1
        if eligible_reviewed:
            stats[class_name]["eligible_reviewed"] += 1
        if reviewed and source in MANUAL_REFERENCE_SOURCES:
            stats[class_name]["manual_reviewed"] += 1
        if reference_allowed:
            stats[class_name]["reference"] += 1
        if reviewed and holdout:
            stats[class_name]["holdout"] += 1
    return total_boxes


def _status_row(class_name: str, counts: Counter[str]) -> dict[str, object]:
    category = category_for_class(class_name)
    reviewed_count = int(counts["reviewed"])
    trainable_reviewed_count = int(counts["trainable_reviewed"])
    eligible_reviewed_count = int(counts["eligible_reviewed"])
    reference_count = int(counts["reference"])
    holdout_count = int(counts["holdout"])
    generated_count = int(counts["generated"])
    generated_cap = max(0, int(max(1, reviewed_count) * GENERATED_CAP_RATIO))
    generated_over_cap = generated_count > generated_cap
    source_issue_count = int(counts["source_issues"])
    ready_for_reference = reference_count >= REFERENCE_MIN_REVIEWED
    ready_for_micro_train = eligible_reviewed_count >= MICRO_TRAIN_MIN_REVIEWED
    ready_for_strong_train = (
        eligible_reviewed_count >= STRONG_TRAIN_MIN_REVIEWED
        and holdout_count >= STRONG_TRAIN_MIN_HOLDOUT
        and not generated_over_cap
        and source_issue_count == 0
    )
    if ready_for_strong_train:
        action = "strong_train"
        message = "Ready for strong candidate training."
    elif ready_for_micro_train:
        action = "micro_train"
        message = "Ready for fast candidate micro-train."
    else:
        action = "reference_only"
        missing = MICRO_TRAIN_MIN_REVIEWED - eligible_reviewed_count
        message = f"Need {missing} more reviewed image(s) before micro-train."
    return {
        "class_name": class_name,
        "class_id": default_class_id_for_name(class_name),
        "command": category.code,
        "bin_index": category.bin_index,
        "route_label": category.name,
        "priority": priority_for_class(class_name),
        "images": int(counts["images"]),
        "trainable_count": int(counts["trainable"]),
        "reviewed_count": reviewed_count,
        "trainable_reviewed_count": trainable_reviewed_count,
        "eligible_reviewed_count": eligible_reviewed_count,
        "manual_reviewed_count": int(counts["manual_reviewed"]),
        "reference_count": reference_count,
        "holdout_count": holdout_count,
        "generated_count": generated_count,
        "generated_cap": generated_cap,
        "generated_over_cap": generated_over_cap,
        "source_issue_count": source_issue_count,
        "missing_for_reference": max(0, REFERENCE_MIN_REVIEWED - reference_count),
        "missing_for_micro_train": max(0, MICRO_TRAIN_MIN_REVIEWED - eligible_reviewed_count),
        "missing_for_strong_train": max(0, STRONG_TRAIN_MIN_REVIEWED - eligible_reviewed_count),
        "missing_holdout_for_strong": max(0, STRONG_TRAIN_MIN_HOLDOUT - holdout_count),
        "ready_for_reference": ready_for_reference,
        "ready_for_micro_train": ready_for_micro_train,
        "ready_for_strong_train": ready_for_strong_train,
        "recommended_action": action,
        "message": message,
    }


__all__ = [
    "MICRO_TRAIN_MIN_REVIEWED",
    "REFERENCE_MIN_REVIEWED",
    "STRONG_TRAIN_MIN_HOLDOUT",
    "STRONG_TRAIN_MIN_REVIEWED",
    "build_learn_now_status",
    "build_selected_learn_now_status",
]
