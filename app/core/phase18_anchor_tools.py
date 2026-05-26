"""Phase 18 helpers for bootstrap review and camera-anchor readiness."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from app.core.dataset_catalog import DatasetCatalog
from app.core.downloaded_zip_intake import (
    DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE,
    has_downloaded_bootstrap_source_metadata,
)
from app.core.waste_categories import canonical_class_name, default_class_id_for_name
from app.core.weak_eval_audit import (
    PHASE16_ANCHOR_TARGETS,
    PHASE16_FOCUS_CLASSES,
    REAL_ANCHOR_SOURCES,
)
from app.core.weak_recovery_filters import WHOLE_IMAGE_COVERAGE_THRESHOLD, strict_recovery_allowed

PHASE18_REVIEW_METHOD = "phase18_assisted_tight_bbox"


def tight_bbox_candidate(image_path: Path, *, threshold: float = WHOLE_IMAGE_COVERAGE_THRESHOLD) -> list[int] | None:
    try:
        rgb = np.asarray(Image.open(image_path).convert("RGB"))
    except OSError:
        return None
    height, width = rgb.shape[:2]
    if width < 32 or height < 32:
        return None
    border = np.concatenate(
        [rgb[:4].reshape(-1, 3), rgb[-4:].reshape(-1, 3), rgb[:, :4].reshape(-1, 3), rgb[:, -4:].reshape(-1, 3)]
    )
    bg = np.median(border, axis=0)
    border_std = float(np.mean(np.std(border, axis=0)))
    dist = np.linalg.norm(rgb.astype(np.float32) - bg.astype(np.float32), axis=2)
    mask = (dist > max(18.0, border_std * 2.0)).astype("uint8")
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    min_area = max(32, int(width * height * 0.0015))
    keep = [idx for idx in range(1, count) if stats[idx, cv2.CC_STAT_AREA] >= min_area]
    if not keep:
        return None
    x1 = max(0, min(int(stats[idx, cv2.CC_STAT_LEFT]) for idx in keep) - 3)
    y1 = max(0, min(int(stats[idx, cv2.CC_STAT_TOP]) for idx in keep) - 3)
    x2 = min(width, max(int(stats[idx, cv2.CC_STAT_LEFT] + stats[idx, cv2.CC_STAT_WIDTH]) for idx in keep) + 3)
    y2 = min(height, max(int(stats[idx, cv2.CC_STAT_TOP] + stats[idx, cv2.CC_STAT_HEIGHT]) for idx in keep) + 3)
    coverage = ((x2 - x1) * (y2 - y1)) / max(1, width * height)
    if coverage <= 0.003 or coverage >= threshold:
        return None
    return [int(x1), int(y1), int(x2), int(y2)]


def review_downloaded_bootstrap(
    queue_dir: Path,
    *,
    catalog_path: Path | None,
    dry_run: bool = False,
    threshold: float = WHOLE_IMAGE_COVERAGE_THRESHOLD,
) -> dict[str, Any]:
    reviewed: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    by_class: Counter[str] = Counter()
    catalog = None if dry_run or catalog_path is None else DatasetCatalog(catalog_path)
    try:
        for image_path in sorted(queue_dir.glob("downloaded_anchor_*.jpg")):
            meta_path = image_path.with_suffix(".json")
            meta = _read_meta(meta_path)
            if str(meta.get("source") or "") != DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE:
                continue
            class_name = _class_name(meta)
            if meta.get("reviewed") is True and meta.get("training_excluded") is not True:
                skipped["already_reviewed"] += 1
                continue
            if not has_downloaded_bootstrap_source_metadata(meta):
                skipped["missing_source_metadata"] += 1
                continue
            bbox = tight_bbox_candidate(image_path, threshold=threshold)
            if bbox is None:
                skipped["no_tight_bbox"] += 1
                continue
            cls_id = default_class_id_for_name(class_name)
            if cls_id is None:
                skipped["unknown_class"] += 1
                continue
            _mark_reviewed(meta, class_name, cls_id, bbox, threshold)
            allowed, reason = strict_recovery_allowed(meta, image_path, threshold=threshold)
            if not allowed:
                skipped[reason or "strict_reject"] += 1
                continue
            if not dry_run:
                meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
                if catalog is not None:
                    catalog.upsert_item(image_path, meta)
            by_class[class_name] += 1
            reviewed.append({"image": str(image_path), "class_name": class_name, "xyxy": bbox})
    finally:
        if catalog is not None:
            catalog.close()
    return {
        "review_method": PHASE18_REVIEW_METHOD,
        "dry_run": dry_run,
        "reviewed_total": len(reviewed),
        "reviewed_by_class": dict(by_class),
        "skipped": dict(skipped),
        "items": reviewed[:200],
    }


def audit_camera_anchor_readiness(queue_dir: Path, *, threshold: float = WHOLE_IMAGE_COVERAGE_THRESHOLD) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    rejection_reasons: Counter[str] = Counter()
    support_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for image_path in sorted(queue_dir.glob("*.jpg")) if queue_dir.exists() else []:
        meta = _read_meta(image_path.with_suffix(".json"))
        classes = _classes(meta)
        if not classes:
            continue
        allowed, reason = strict_recovery_allowed(meta, image_path, threshold=threshold)
        if reason:
            rejection_reasons[reason] += 1
        source = str(meta.get("source") or "unknown")
        for class_name in classes:
            if class_name not in PHASE16_FOCUS_CLASSES:
                continue
            support_counts[class_name][f"source:{source}"] += 1
            support_counts[class_name]["strict_allowed"] += int(allowed)
        if allowed:
            items.append({"source": source, "split": str(meta.get("split") or "train"), "classes": sorted(classes)})
    rows = _readiness_rows(items, support_counts)
    missing = {name: row["missing_real_anchor"] for name, row in rows.items() if row["missing_real_anchor"] > 0}
    return {
        "generated_at": datetime.now().isoformat(),
        "coverage_threshold": threshold,
        "train_allowed": not missing,
        "missing_anchor_targets": missing,
        "classes": rows,
        "rejection_reasons": dict(rejection_reasons),
    }


def _mark_reviewed(meta: dict[str, Any], class_name: str, cls_id: int, bbox: list[int], threshold: float) -> None:
    meta["boxes"] = [{"cls_id": cls_id, "cls_name": class_name, "conf": 1.0, "xyxy": bbox}]
    meta["reviewed"] = True
    meta["bbox_reviewed"] = True
    meta["needs_annotation"] = False
    meta["training_excluded"] = False
    meta["recognition_enabled"] = False
    meta["split"] = "train"
    meta["split_lock"] = True
    meta["weak_full_image_bbox"] = False
    meta["phase18_reviewed_train_support"] = True
    meta["review_method"] = PHASE18_REVIEW_METHOD
    meta["reviewed_at"] = datetime.now().isoformat()
    meta["coverage_threshold"] = threshold
    meta["training_exclusion_reason_previous"] = meta.pop("training_exclusion_reason", "")


def _readiness_rows(items: list[dict[str, Any]], support_counts: dict[str, Counter[str]]) -> dict[str, Any]:
    real_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for item in items:
        source = str(item.get("source") or "unknown")
        for class_name in item.get("classes", []):
            if class_name in PHASE16_FOCUS_CLASSES and source in REAL_ANCHOR_SOURCES:
                real_counts[class_name]["real_anchor"] += 1
    rows = {}
    for class_name in PHASE16_FOCUS_CLASSES:
        target = PHASE16_ANCHOR_TARGETS.get(class_name, 0)
        real_anchor = int(real_counts[class_name]["real_anchor"])
        rows[class_name] = {
            "target_real_anchor": target,
            "real_anchor": real_anchor,
            "missing_real_anchor": max(0, target - real_anchor),
            **dict(support_counts[class_name]),
        }
    return rows


def _classes(meta: dict[str, Any]) -> set[str]:
    return {
        canonical_class_name(str(box.get("cls_name") or meta.get("canonical_class") or ""))
        for box in meta.get("boxes") or []
        if isinstance(box, dict)
    }


def _class_name(meta: dict[str, Any]) -> str:
    boxes = meta.get("boxes") or [{}]
    return canonical_class_name(str(meta.get("canonical_class") or boxes[0].get("cls_name") or ""))


def _read_meta(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}
