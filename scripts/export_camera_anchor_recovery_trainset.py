"""Export camera-anchor recovery trainset with real-anchor safeguards."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.balanced_trainset import export_balanced_trainset  # noqa: E402
from app.core.waste_categories import TRAINING_CLASS_ORDER_45, canonical_class_name  # noqa: E402
from app.core.weak_eval_audit import (  # noqa: E402
    PHASE16_ANCHOR_TARGETS,
    PHASE16_FOCUS_CLASSES,
    REAL_ANCHOR_SOURCES,
    TRAIN_SUPPORT_SOURCES,
    source_anchor_counts,
)
from app.core.weak_recovery_filters import (  # noqa: E402
    WHOLE_IMAGE_COVERAGE_THRESHOLD,
    strict_recovery_allowed,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--out", type=Path, default=Path("dataset_v2/yolo_camera_anchor_recovery_v4"))
    parser.add_argument("--max-images", type=int, default=8200)
    parser.add_argument("--legacy-quota", type=int, default=330)
    parser.add_argument("--min-box-area", type=float, default=0.001)
    parser.add_argument("--min-box-side", type=float, default=0.005)
    parser.add_argument("--coverage-threshold", type=float, default=WHOLE_IMAGE_COVERAGE_THRESHOLD)
    parser.add_argument("--seed", type=int, default=43)
    args = parser.parse_args()

    staging = args.out / "_camera_anchor_queue"
    stage_stats = _stage_camera_anchor_queue(args.queue, staging, args.coverage_threshold)
    export_stats = export_balanced_trainset(
        staging,
        args.out,
        TRAINING_CLASS_ORDER_45,
        max_images=args.max_images,
        legacy_quota=args.legacy_quota,
        focus_classes=PHASE16_FOCUS_CLASSES,
        min_box_area=args.min_box_area,
        min_box_side=args.min_box_side,
        require_reviewed=False,
        generated_cap_ratio=0.0,
        seed=args.seed,
    )
    export_stats["camera_anchor_stage"] = stage_stats
    report_path = args.out / "export_report.json"
    report_path.write_text(json.dumps(export_stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Camera-anchor trainset: {export_stats['images']} images / {export_stats['boxes']} boxes")
    print(f"Report: {report_path}")
    return 0


def _stage_camera_anchor_queue(queue_dir: Path, staging: Path, threshold: float) -> dict[str, Any]:
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    reasons: Counter[str] = Counter()
    accepted = 0
    staged_items: list[dict[str, Any]] = []
    anchor_indexes: dict[str, int] = defaultdict(int)
    for image_path in sorted(queue_dir.glob("*.jpg")) if queue_dir.exists() else []:
        if not image_path.exists():
            continue
        meta_path = image_path.with_suffix(".json")
        if not meta_path.exists():
            continue
        meta = _read_meta(meta_path)
        allowed, reason = strict_recovery_allowed(meta, image_path, threshold=threshold)
        if not allowed:
            reasons[reason or "rejected"] += 1
            continue
        staged_meta = dict(meta)
        classes = _classes(staged_meta)
        source = str(staged_meta.get("source") or "unknown")
        if source in TRAIN_SUPPORT_SOURCES:
            staged_meta["split"] = "train"
            staged_meta["split_lock"] = True
            staged_meta["phase16_train_support"] = True
            staged_meta["phase17_downloaded_train_support"] = source == "downloaded_anchor_bootstrap"
        elif source in REAL_ANCHOR_SOURCES and classes & set(PHASE16_FOCUS_CLASSES):
            anchor_class = sorted(classes & set(PHASE16_FOCUS_CLASSES))[0]
            staged_meta["split"] = _anchor_split(anchor_indexes[anchor_class])
            staged_meta["split_lock"] = True
            staged_meta["phase16_camera_anchor"] = True
            anchor_indexes[anchor_class] += 1
        shutil.copy2(image_path, staging / image_path.name)
        (staging / meta_path.name).write_text(json.dumps(staged_meta, indent=2, ensure_ascii=False), encoding="utf-8")
        staged_items.append(
            {
                "source": source,
                "split": str(staged_meta.get("split") or "train"),
                "classes": sorted(classes),
            }
        )
        accepted += 1
    anchor_counts = source_anchor_counts(staged_items, PHASE16_FOCUS_CLASSES)
    missing = {
        name: row["missing_real_anchor"]
        for name, row in anchor_counts.items()
        if row["missing_real_anchor"] > 0 and PHASE16_ANCHOR_TARGETS.get(name, 0) > 0
    }
    return {
        "accepted_images": accepted,
        "rejected_images": sum(reasons.values()),
        "rejection_reasons": dict(reasons),
        "coverage_threshold": threshold,
        "anchor_counts": anchor_counts,
        "missing_anchor_targets": missing,
    }


def _classes(meta: dict[str, Any]) -> set[str]:
    return {
        canonical_class_name(str(box.get("cls_name") or ""))
        for box in meta.get("boxes") or []
        if isinstance(box, dict)
    }


def _anchor_split(index: int) -> str:
    if index % 5 == 0:
        return "valid"
    if index % 5 == 1:
        return "test"
    return "train"


def _read_meta(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
