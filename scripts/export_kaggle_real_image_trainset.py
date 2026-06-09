"""Export Phase 20 Kaggle real-image candidate trainset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.balanced_trainset import export_balanced_trainset  # noqa: E402
from app.core.waste_categories import TRAINING_CLASS_ORDER_45  # noqa: E402
from app.core.weak_eval_audit import PHASE16_FOCUS_CLASSES  # noqa: E402
from app.core.weak_recovery_filters import WHOLE_IMAGE_COVERAGE_THRESHOLD  # noqa: E402
from scripts.export_camera_anchor_recovery_trainset import _stage_camera_anchor_queue  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2") / "low_conf_queue")
    parser.add_argument("--out", type=Path, default=Path("dataset_v2") / "yolo_kaggle_real_image_v5")
    parser.add_argument("--max-images", type=int, default=11000)
    parser.add_argument("--legacy-quota", type=int, default=360)
    parser.add_argument("--min-box-area", type=float, default=0.001)
    parser.add_argument("--min-box-side", type=float, default=0.005)
    parser.add_argument("--coverage-threshold", type=float, default=WHOLE_IMAGE_COVERAGE_THRESHOLD)
    parser.add_argument("--seed", type=int, default=44)
    args = parser.parse_args()

    staging = args.out / "_kaggle_real_image_queue"
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
    export_stats["phase20_kaggle_stage"] = stage_stats
    report_path = args.out / "export_report.json"
    report_path.write_text(json.dumps(export_stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Kaggle real-image trainset: {export_stats['images']} images / {export_stats['boxes']} boxes")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
