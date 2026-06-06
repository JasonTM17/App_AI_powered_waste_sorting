"""Export a balanced 45-class dataset for the fast Pen fine-tune."""

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--out", type=Path, default=Path("dataset_v2/yolo_fast_pen"))
    parser.add_argument("--max-images", type=int, default=4500)
    parser.add_argument("--legacy-quota", type=int, default=75)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    stats = export_balanced_trainset(
        args.queue,
        args.out,
        TRAINING_CLASS_ORDER_45,
        max_images=args.max_images,
        legacy_quota=args.legacy_quota,
        seed=args.seed,
    )
    report = args.out / "export_report.json"
    report.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Fast trainset: {stats['images']} images / {stats['boxes']} boxes")
    print(f"Report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
