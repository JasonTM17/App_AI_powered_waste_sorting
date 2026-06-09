"""Audit Phase 15 weak targets and conservatively repair tight web bboxes."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.dataset_catalog import DatasetCatalog  # noqa: E402
from app.core.dataset_queue import is_trainable_meta  # noqa: E402
from app.core.waste_categories import canonical_class_name  # noqa: E402
from app.core.weak_recovery_filters import (  # noqa: E402
    PHASE15_FOCUS_CLASSES,
    WEAK_TARGET_BOX_COUNTS,
    bbox_coverages,
    has_complete_web_license,
    strict_recovery_allowed,
)

REPAIR_METHOD = "phase15_tight_bbox_repair"


def audit_targets(
    queue_dir: Path,
    *,
    report_path: Path | None = None,
    repair: bool = False,
    catalog_path: Path | None = None,
    threshold: float = 0.92,
) -> dict[str, Any]:
    repaired = _repair_queue(queue_dir, catalog_path, threshold) if repair else []
    report = _build_report(queue_dir, threshold)
    report["repair"] = {"enabled": repair, "count": len(repaired), "items": repaired[:100]}
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _build_report(queue_dir: Path, threshold: float) -> dict[str, Any]:
    rows: dict[str, Counter[str]] = defaultdict(Counter)
    rejection_reasons: Counter[str] = Counter()
    total_images = 0
    for image_path in sorted(queue_dir.glob("*.jpg")) if queue_dir.exists() else []:
        meta = _read_meta(image_path.with_suffix(".json"))
        if not meta:
            continue
        total_images += 1
        strict_allowed, reason = strict_recovery_allowed(meta, image_path, threshold=threshold)
        if reason:
            rejection_reasons[reason] += 1
        holdout = meta.get("holdout") is True or str(meta.get("split") or "").lower() == "test"
        trainable_reviewed = is_trainable_meta(meta) and meta.get("reviewed") is True
        for class_name, coverage in bbox_coverages(meta, image_path):
            if class_name not in PHASE15_FOCUS_CLASSES:
                continue
            row = rows[class_name]
            row["boxes"] += 1
            row["trainable_reviewed"] += int(trainable_reviewed)
            row["quarantined"] += int(meta.get("training_excluded") is True)
            row["holdout"] += int(holdout)
            row["full_image_bbox"] += int(coverage >= threshold)
            row["true_bbox"] += int(strict_allowed and coverage < threshold)
            row["repaired"] += int(meta.get("phase15_repaired") is True)
    class_rows = []
    for class_name in PHASE15_FOCUS_CLASSES:
        counts = rows[class_name]
        target = WEAK_TARGET_BOX_COUNTS.get(class_name, 0)
        true_bbox = int(counts["true_bbox"])
        class_rows.append(
            {
                "class_name": class_name,
                "target_true_bbox": target,
                "boxes": int(counts["boxes"]),
                "true_bbox": true_bbox,
                "missing_target": max(0, target - true_bbox),
                "trainable_reviewed": int(counts["trainable_reviewed"]),
                "quarantined": int(counts["quarantined"]),
                "holdout": int(counts["holdout"]),
                "full_image_bbox": int(counts["full_image_bbox"]),
                "repaired": int(counts["repaired"]),
            }
        )
    return {
        "queue_dir": str(queue_dir.resolve()),
        "generated_at": datetime.now().isoformat(),
        "coverage_threshold": threshold,
        "total_images": total_images,
        "classes": class_rows,
        "rejection_reasons": dict(rejection_reasons),
    }


def _repair_queue(queue_dir: Path, catalog_path: Path | None, threshold: float) -> list[dict[str, Any]]:
    catalog = DatasetCatalog(catalog_path) if catalog_path is not None else None
    repaired: list[dict[str, Any]] = []
    try:
        for image_path in sorted(queue_dir.glob("manual_web_*.jpg")):
            meta_path = image_path.with_suffix(".json")
            meta = _read_meta(meta_path)
            classes = _single_focus_class(meta)
            if not classes or not _repairable_meta(meta):
                continue
            bbox = _tight_bbox_candidate(image_path, threshold)
            if bbox is None:
                continue
            class_name = next(iter(classes))
            _apply_repair(meta, bbox, class_name)
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            if catalog is not None:
                catalog.upsert_item(image_path, meta)
            repaired.append({"image": str(image_path), "class_name": class_name, "xyxy": bbox})
    finally:
        if catalog is not None:
            catalog.close()
    return repaired


def _repairable_meta(meta: dict[str, Any]) -> bool:
    pending_web_review = meta.get("needs_annotation") is True or meta.get("reviewed") is not True
    return (
        str(meta.get("source") or "") == "manual_web_import"
        and (meta.get("training_excluded") is True or pending_web_review)
        and has_complete_web_license(meta)
        and not bool(meta.get("generated"))
    )


def _single_focus_class(meta: dict[str, Any]) -> set[str]:
    classes = {
        canonical_class_name(str(box.get("cls_name") or ""))
        for box in meta.get("boxes") or []
        if isinstance(box, dict)
    }
    return {name for name in classes if name in WEAK_TARGET_BOX_COUNTS} if len(classes) == 1 else set()


def _apply_repair(meta: dict[str, Any], bbox: list[int], class_name: str) -> None:
    for box in meta.get("boxes") or []:
        if isinstance(box, dict):
            box["xyxy"] = bbox
            box["cls_name"] = class_name
            box["conf"] = 1.0
    meta["reviewed"] = True
    meta["needs_annotation"] = False
    meta["training_excluded"] = False
    meta["recognition_enabled"] = True
    meta["phase15_repaired"] = True
    meta["review_method"] = REPAIR_METHOD
    meta["reviewed_at"] = datetime.now().isoformat()
    meta["training_exclusion_reason_previous"] = meta.pop("training_exclusion_reason", "")


def _tight_bbox_candidate(image_path: Path, threshold: float) -> list[int] | None:
    try:
        rgb = np.asarray(Image.open(image_path).convert("RGB"))
    except OSError:
        return None
    height, width = rgb.shape[:2]
    border = np.concatenate([rgb[:3].reshape(-1, 3), rgb[-3:].reshape(-1, 3), rgb[:, :3].reshape(-1, 3), rgb[:, -3:].reshape(-1, 3)])
    if float(np.mean(np.std(border, axis=0))) > 34.0:
        return None
    bg = np.median(border, axis=0)
    dist = np.linalg.norm(rgb.astype(np.float32) - bg.astype(np.float32), axis=2)
    mask = (dist > max(24.0, float(np.mean(np.std(border, axis=0))) * 2.4)).astype("uint8")
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, 8)
    keep = [i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= max(24, int(width * height * 0.002))]
    if not keep:
        return None
    xs, ys, xe, ye = [], [], [], []
    for idx in keep:
        x, y, w, h, _area = stats[idx]
        xs.append(x)
        ys.append(y)
        xe.append(x + w)
        ye.append(y + h)
    x1, y1, x2, y2 = max(0, min(xs) - 2), max(0, min(ys) - 2), min(width, max(xe) + 2), min(height, max(ye) + 2)
    coverage = ((x2 - x1) * (y2 - y1)) / max(1, width * height)
    if coverage <= 0.01 or coverage >= threshold:
        return None
    return [int(x1), int(y1), int(x2), int(y2)]


def _read_meta(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--catalog", type=Path, default=Path("dataset_v2/dataset.db"))
    parser.add_argument("--report", type=Path, default=Path("dataset_v2/phase15_weak_recovery_audit.json"))
    parser.add_argument("--coverage-threshold", type=float, default=0.92)
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()
    report = audit_targets(
        args.queue,
        report_path=args.report,
        repair=args.repair,
        catalog_path=args.catalog,
        threshold=args.coverage_threshold,
    )
    print(f"Weak recovery audit: {report['total_images']} images, repair={report['repair']['count']}")
    print(f"Report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
