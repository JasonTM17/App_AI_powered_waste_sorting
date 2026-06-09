"""Export Phase 15 strict weak-recovery v2 trainset."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.balanced_trainset import export_balanced_trainset  # noqa: E402
from app.core.waste_categories import TRAINING_CLASS_ORDER_45  # noqa: E402
from app.core.weak_recovery_filters import (  # noqa: E402
    PHASE15_FOCUS_CLASSES,
    WHOLE_IMAGE_COVERAGE_THRESHOLD,
    strict_recovery_allowed,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--out", type=Path, default=Path("dataset_v2/yolo_weak_recovery_v2"))
    parser.add_argument("--max-images", type=int, default=8500)
    parser.add_argument("--legacy-quota", type=int, default=360)
    parser.add_argument("--min-box-area", type=float, default=0.001)
    parser.add_argument("--min-box-side", type=float, default=0.005)
    parser.add_argument("--coverage-threshold", type=float, default=WHOLE_IMAGE_COVERAGE_THRESHOLD)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    staging = args.out / "_strict_queue"
    stats = _stage_strict_queue(args.queue, staging, args.coverage_threshold)
    export_stats = export_balanced_trainset(
        staging,
        args.out,
        TRAINING_CLASS_ORDER_45,
        max_images=args.max_images,
        legacy_quota=args.legacy_quota,
        focus_classes=PHASE15_FOCUS_CLASSES,
        min_box_area=args.min_box_area,
        min_box_side=args.min_box_side,
        require_reviewed=False,
        generated_cap_ratio=0.0,
        seed=args.seed,
    )
    export_stats["strict_stage"] = stats
    report = args.out / "export_report.json"
    report.write_text(json.dumps(export_stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Weak recovery v2 trainset: {export_stats['images']} images / {export_stats['boxes']} boxes")
    print(f"Report: {report}")
    return 0


def _stage_strict_queue(queue_dir: Path, staging: Path, threshold: float) -> dict[str, object]:
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    reasons: Counter[str] = Counter()
    accepted = 0
    for image_path in sorted(queue_dir.glob("*.jpg")) if queue_dir.exists() else []:
        meta_path = image_path.with_suffix(".json")
        meta = _read_meta(meta_path)
        allowed, reason = strict_recovery_allowed(meta, image_path, threshold=threshold)
        if not allowed:
            reasons[reason or "rejected"] += 1
            continue
        shutil.copy2(image_path, staging / image_path.name)
        shutil.copy2(meta_path, staging / meta_path.name)
        accepted += 1
    return {
        "accepted_images": accepted,
        "rejected_images": sum(reasons.values()),
        "rejection_reasons": dict(reasons),
        "coverage_threshold": threshold,
    }


def _read_meta(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
