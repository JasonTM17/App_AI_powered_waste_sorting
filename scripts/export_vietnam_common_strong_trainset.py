"""Export the Phase 8 strong Vietnamese common-waste candidate dataset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.balanced_trainset import export_balanced_trainset  # noqa: E402
from app.core.vietnam_waste_targets import VIETNAM_TARGET_CLASSES  # noqa: E402
from app.core.waste_categories import TRAINING_CLASS_ORDER_45  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--out", type=Path, default=Path("dataset_v2/yolo_strong_vietnam_common_v1"))
    parser.add_argument("--max-images", type=int, default=14000)
    parser.add_argument("--legacy-quota", type=int, default=220)
    parser.add_argument("--min-box-area", type=float, default=0.001)
    parser.add_argument("--min-box-side", type=float, default=0.005)
    parser.add_argument("--require-reviewed", action="store_true")
    parser.add_argument("--generated-cap-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    stats = export_balanced_trainset(
        args.queue,
        args.out,
        TRAINING_CLASS_ORDER_45,
        max_images=args.max_images,
        legacy_quota=args.legacy_quota,
        focus_classes=VIETNAM_TARGET_CLASSES,
        min_box_area=args.min_box_area,
        min_box_side=args.min_box_side,
        require_reviewed=args.require_reviewed,
        generated_cap_ratio=args.generated_cap_ratio,
        seed=args.seed,
    )
    report = args.out / "export_report.json"
    report.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Vietnam strong trainset: {stats['images']} images / {stats['boxes']} boxes")
    print(f"Report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
