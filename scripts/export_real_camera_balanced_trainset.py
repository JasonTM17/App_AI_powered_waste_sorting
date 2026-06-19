"""Export a balanced YOLO trainset that always preserves reviewed camera captures."""

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

REAL_CAMERA_SOURCES = ("manual_camera_capture", "capture_session")
CAMERA_FOCUS_CLASSES = (
    "Iron utensils",
    "Pen",
    "Disposable tableware",
    "Electronics",
    "Wood",
    "Textile",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--out", type=Path, default=Path("dataset_v2/yolo_real_camera_balanced"))
    parser.add_argument("--max-images", type=int, default=9000)
    parser.add_argument("--legacy-quota", type=int, default=180)
    parser.add_argument("--focus-quota", type=int, default=900)
    parser.add_argument("--seed", type=int, default=619)
    args = parser.parse_args()

    stats = export_balanced_trainset(
        args.queue,
        args.out,
        TRAINING_CLASS_ORDER_45,
        max_images=args.max_images,
        legacy_quota=args.legacy_quota,
        focus_classes=CAMERA_FOCUS_CLASSES,
        focus_quota=args.focus_quota,
        min_box_area=0.001,
        min_box_side=0.005,
        priority_sources=REAL_CAMERA_SOURCES,
        generated_cap_ratio=0.0,
        seed=args.seed,
    )
    report = args.out / "export_report.json"
    report.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Camera-balanced trainset: {stats['images']} images / {stats['boxes']} boxes")
    print(f"Reviewed camera captures are prioritized from: {', '.join(REAL_CAMERA_SOURCES)}")
    print(f"Report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
