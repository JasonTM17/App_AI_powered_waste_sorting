"""Export a manifest dataset for the Phase 21 Kaggle O/R/I classifier."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.kaggle_intake import (  # noqa: E402
    KAGGLE_GARBAGE_DETECTION_VN_SOURCE,
    KAGGLE_MINI_TRASH_VIETNAM_SOURCE,
)
from app.core.kaggle_real_image_pipeline import read_manifest  # noqa: E402
from app.core.waste_categories import category_for_class  # noqa: E402

KAGGLE_YOLO_CROP_SOURCES = {
    KAGGLE_GARBAGE_DETECTION_VN_SOURCE,
    KAGGLE_MINI_TRASH_VIETNAM_SOURCE,
    "roboflow_3kelas_v1",
    "roboflow_wastebasket_can_bottle_v3",
}
BIN_ORDER = ("O", "R", "I")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("dataset_v2") / "phase20_kaggle_classification_manifest.jsonl",
    )
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2") / "low_conf_queue")
    parser.add_argument("--out", type=Path, default=Path("dataset_v2") / "kaggle_three_bin_classifier_v1")
    parser.add_argument("--max-per-bin", type=int, default=0, help="0 means no cap.")
    parser.add_argument("--max-per-class", type=int, default=0, help="0 means no cap.")
    parser.add_argument("--include-yolo-crops", action="store_true")
    parser.add_argument("--crop-max-per-bin", type=int, default=1200)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    rows = _manifest_rows(
        args.manifest,
        max_per_bin=args.max_per_bin,
        max_per_class=args.max_per_class,
    )
    crop_rows: list[dict[str, object]] = []
    if args.include_yolo_crops:
        crop_rows = _yolo_crop_rows(args.queue, args.out / "crops", max_per_bin=args.crop_max_per_bin)
    all_rows = [*rows, *crop_rows]
    split_counts: Counter[str] = Counter()
    bin_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    for split in ("train", "valid", "test"):
        split_rows = [row for row in all_rows if row["split"] == split]
        (args.out / f"{split}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in split_rows),
            encoding="utf-8",
        )
        split_counts[split] = len(split_rows)
    for row in all_rows:
        bin_counts[str(row["bin_code"])] += 1
        source_counts[str(row.get("source_dataset") or row.get("source_name") or "")] += 1
    report = {
        "dataset_dir": str(args.out),
        "manifest": str(args.manifest),
        "images": len(all_rows),
        "from_classification_manifest": len(rows),
        "from_yolo_crops": len(crop_rows),
        "by_split": dict(sorted(split_counts.items())),
        "by_bin": dict(sorted(bin_counts.items())),
        "by_source": dict(sorted(source_counts.items())),
        "classes": list(BIN_ORDER),
        "classification_only_not_yolo": True,
    }
    (args.out / "export_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def _manifest_rows(
    manifest: Path,
    *,
    max_per_bin: int,
    max_per_class: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    bin_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    for row in read_manifest(manifest):
        bin_code = str(row.get("bin_code") or "")
        canonical_class = str(row.get("canonical_class") or "")
        source_path = Path(str(row.get("source_path") or ""))
        if bin_code not in BIN_ORDER or not source_path.exists():
            continue
        if max_per_bin > 0 and bin_counts[bin_code] >= max_per_bin:
            continue
        if max_per_class > 0 and class_counts[canonical_class] >= max_per_class:
            continue
        split = str(row.get("classifier_split") or "train").lower()
        if split not in {"train", "valid", "test"}:
            split = "train"
        rows.append(
            {
                "image_path": str(source_path),
                "split": split,
                "bin_code": bin_code,
                "canonical_class": canonical_class,
                "source_dataset": row.get("source_dataset"),
                "source_class": row.get("source_class"),
                "bbox_status": "missing",
                "input_type": "classification_image",
            }
        )
        bin_counts[bin_code] += 1
        class_counts[canonical_class] += 1
    return rows


def _yolo_crop_rows(queue: Path, crop_dir: Path, *, max_per_bin: int) -> list[dict[str, object]]:
    if crop_dir.exists():
        shutil.rmtree(crop_dir)
    crop_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    bin_counts: Counter[str] = Counter()
    if not queue.exists():
        return rows
    for meta_path in sorted(queue.glob("*.json")):
        meta = _read_meta(meta_path)
        source = str(meta.get("source") or "")
        if source not in KAGGLE_YOLO_CROP_SOURCES:
            continue
        image_path = meta_path.with_suffix(".jpg")
        if not image_path.exists():
            continue
        for box_index, box in enumerate(meta.get("boxes") or []):
            if not isinstance(box, dict):
                continue
            cls_name = str(box.get("cls_name") or "")
            category = category_for_class(cls_name)
            if max_per_bin > 0 and bin_counts[category.code] >= max_per_bin:
                continue
            crop_path = crop_dir / category.code / f"{image_path.stem}_{box_index}_{uuid.uuid4().hex[:8]}.jpg"
            if not _write_crop(image_path, crop_path, box.get("xyxy") or []):
                continue
            rows.append(
                {
                    "image_path": str(crop_path),
                    "split": "train",
                    "bin_code": category.code,
                    "canonical_class": cls_name,
                    "source_name": source,
                    "source_dataset": meta.get("source_dataset"),
                    "bbox_status": "real_bbox_crop",
                    "input_type": "yolo_bbox_crop",
                }
            )
            bin_counts[category.code] += 1
    return rows


def _write_crop(image_path: Path, out: Path, xyxy: list[Any]) -> bool:
    if len(xyxy) < 4:
        return False
    try:
        with Image.open(image_path) as image:
            width, height = image.size
            x1, y1, x2, y2 = (int(float(str(value))) for value in xyxy[:4])
            crop_box = (
                max(0, min(width - 1, x1)),
                max(0, min(height - 1, y1)),
                max(1, min(width, x2)),
                max(1, min(height, y2)),
            )
            if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
                return False
            out.parent.mkdir(parents=True, exist_ok=True)
            image.crop(crop_box).convert("RGB").save(out, format="JPEG", quality=92)
            return True
    except (OSError, ValueError, TypeError):
        return False


def _read_meta(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
