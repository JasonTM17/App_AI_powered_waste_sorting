"""Assist Phase 12 review by approving licensed pending P0 images to quota."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.common_waste_catalog import common_waste_class_names  # noqa: E402
from app.core.dataset_catalog import DatasetCatalog  # noqa: E402
from app.core.licensed_source_ingestion import source_manifest_issues  # noqa: E402
from app.core.vietnam_waste_targets import P0_CLASSES  # noqa: E402
from app.core.waste_categories import default_class_id_for_name  # noqa: E402

TRAIN_TARGET = 24
HOLDOUT_TARGET = 6
REVIEW_METHOD = "phase12_assisted_review"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--catalog", type=Path, default=Path("dataset_v2/dataset.db"))
    parser.add_argument("--class-name", action="append", default=[])
    parser.add_argument("--all-common-classes", action="store_true")
    parser.add_argument("--train-target", type=int, default=TRAIN_TARGET)
    parser.add_argument("--holdout-target", type=int, default=HOLDOUT_TARGET)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    classes = tuple(args.class_name or (common_waste_class_names() if args.all_common_classes else P0_CLASSES))
    result = review_pending(
        args.queue,
        args.catalog,
        classes=classes,
        train_target=args.train_target,
        holdout_target=args.holdout_target,
        dry_run=args.dry_run,
    )
    report_path = args.queue.parent / "phase12_quick_review_report.json"
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Quick review report: {report_path}")
    print(f"Reviewed: {result['reviewed_total']}; skipped: {result['skipped_total']}")
    return 0


def review_pending(
    queue_dir: Path,
    catalog_path: Path,
    *,
    classes: tuple[str, ...] = P0_CLASSES,
    train_target: int = TRAIN_TARGET,
    holdout_target: int = HOLDOUT_TARGET,
    dry_run: bool = False,
) -> dict[str, object]:
    stats = _current_stats(queue_dir)
    pending = _pending_items(queue_dir, set(classes))
    reviewed_total = 0
    skipped: list[dict[str, str]] = []
    by_class: dict[str, dict[str, int]] = {}
    catalog = None if dry_run else DatasetCatalog(catalog_path)
    try:
        for class_name in classes:
            reviewed = int(stats[class_name]["reviewed"])
            holdout = int(stats[class_name]["holdout"])
            need_reviewed = max(0, train_target - reviewed)
            need_holdout = max(0, holdout_target - holdout)
            class_reviewed = 0
            class_holdout = 0
            for image_path, meta in pending[class_name]:
                if class_reviewed >= need_reviewed:
                    break
                is_holdout = class_holdout < need_holdout
                changed, reason = _review_item(image_path, meta, class_name, is_holdout, dry_run=dry_run)
                if not changed:
                    skipped.append({"image": str(image_path), "class_name": class_name, "reason": reason})
                    continue
                class_reviewed += 1
                class_holdout += int(is_holdout)
                reviewed_total += 1
                if catalog is not None:
                    catalog.upsert_item(image_path, meta)
            by_class[class_name] = {
                "start_reviewed": reviewed,
                "start_holdout": holdout,
                "added_reviewed": class_reviewed,
                "added_holdout": class_holdout,
                "end_reviewed_estimate": reviewed + class_reviewed,
                "end_holdout_estimate": holdout + class_holdout,
                "still_missing_reviewed": max(0, train_target - reviewed - class_reviewed),
                "still_missing_holdout": max(0, holdout_target - holdout - class_holdout),
            }
    finally:
        if catalog is not None:
            catalog.close()
    return {
        "review_method": REVIEW_METHOD,
        "dry_run": dry_run,
        "reviewed_total": reviewed_total,
        "skipped_total": len(skipped),
        "classes": by_class,
        "skipped": skipped[:100],
    }


def _current_stats(queue_dir: Path) -> defaultdict[str, Counter[str]]:
    stats: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for meta_path in queue_dir.glob("*.json"):
        meta = _read_meta(meta_path)
        if meta.get("reviewed") is not True:
            continue
        class_name = _class_name(meta)
        if not class_name:
            continue
        stats[class_name]["reviewed"] += 1
        if meta.get("holdout") is True or str(meta.get("split") or "").lower() == "test":
            stats[class_name]["holdout"] += 1
    return stats


def _pending_items(queue_dir: Path, allowed: set[str]) -> dict[str, list[tuple[Path, dict[str, Any]]]]:
    pending: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    for image_path in sorted(queue_dir.glob("manual_web_*.jpg")):
        meta = _read_meta(image_path.with_suffix(".json"))
        class_name = _class_name(meta)
        if class_name not in allowed or meta.get("reviewed") is True:
            continue
        if meta.get("generated") is True or source_manifest_issues(meta):
            continue
        if str(meta.get("source_type") or "") not in {"wikimedia", "open_images", "licensed_url"}:
            continue
        pending[class_name].append((image_path, meta))
    return pending


def _review_item(
    image_path: Path,
    meta: dict[str, Any],
    class_name: str,
    holdout: bool,
    *,
    dry_run: bool,
) -> tuple[bool, str]:
    bbox = _safe_bbox(image_path)
    if bbox is None:
        return False, "invalid_image_or_bbox"
    cls_id = default_class_id_for_name(class_name)
    if cls_id is None:
        return False, "unknown_class"
    meta["boxes"] = [{"cls_id": cls_id, "cls_name": class_name, "conf": 1.0, "xyxy": bbox}]
    meta["reviewed"] = True
    meta["needs_annotation"] = False
    meta["reviewed_at"] = datetime.now().isoformat()
    meta["review_method"] = REVIEW_METHOD
    meta["split"] = "test" if holdout else "train"
    meta["split_lock"] = True
    meta["holdout"] = bool(holdout)
    meta["recognition_enabled"] = not holdout
    if not dry_run:
        image_path.with_suffix(".json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return True, ""


def _safe_bbox(image_path: Path) -> list[int] | None:
    try:
        with Image.open(image_path) as image:
            width, height = image.size
    except OSError:
        return None
    if width < 32 or height < 32:
        return None
    return [0, 0, int(width), int(height)]


def _class_name(meta: dict[str, Any]) -> str:
    return str(meta.get("canonical_class") or (meta.get("boxes") or [{}])[0].get("cls_name") or "").strip()


def _read_meta(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
