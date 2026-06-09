"""Audit and safely import Kaggle Vietnam waste datasets.

The importer only auto-imports YOLO detection datasets with mapped labels. Image
classification folders are reported as needing bbox review and are not treated as
detection training data.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.dataset_catalog import DatasetCatalog  # noqa: E402
from app.core.kaggle_intake import (  # noqa: E402
    KAGGLE_DATASETS,
    likely_dataset_kind,
    source_for_kaggle_ref,
)
from app.core.waste_categories import TRAINING_CLASS_ORDER_45  # noqa: E402
from app.utils.dataset_import import (  # noqa: E402
    import_yolo_dataset_to_queue,
    label_map_for_preset,
    read_yolo_dataset_names,
)
from app.utils.paths import dataset_db_path  # noqa: E402

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
LABEL_EXTS = {".txt"}
REPORT_DIR = Path("dataset_v2")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path, help="Downloaded Kaggle dataset folder.")
    parser.add_argument("--kaggle-ref", default="hoaalan/mini-trash-dataset-in-vietnam")
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--catalog", type=Path, default=dataset_db_path())
    parser.add_argument("--report", type=Path, default=REPORT_DIR / "phase19_kaggle_intake_report.json")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-large",
        action="store_true",
        help="Allow importing datasets above the default image-count safety cap.",
    )
    parser.add_argument("--max-auto-import-images", type=int, default=1500)
    parser.add_argument("--no-resume", action="store_true", help="Do not skip existing original_file rows.")
    args = parser.parse_args()

    source_name = source_for_kaggle_ref(args.kaggle_ref)
    label_map = label_map_for_preset("kaggle_vietnam_waste") or {}
    class_map = {name: index for index, name in enumerate(TRAINING_CLASS_ORDER_45)}
    audit = audit_kaggle_dataset(args.dataset, args.kaggle_ref, source_name, label_map)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    import_result: dict[str, Any] = {"attempted": False, "imported": 0}
    if audit["can_auto_import"] and not args.dry_run:
        existing_originals = set() if args.no_resume else _existing_original_files(args.queue, source_name)
        requested_images = min(int(audit["image_count"]), args.limit or int(audit["image_count"]))
        if requested_images > args.max_auto_import_images and not args.allow_large:
            import_result = {
                "attempted": False,
                "imported": 0,
                "skipped_reason": "image_count_exceeds_auto_import_cap",
                "max_auto_import_images": args.max_auto_import_images,
                "requested_images": requested_images,
            }
        else:
            imported = import_yolo_dataset_to_queue(
                args.dataset,
                args.queue,
                source_name=source_name,
                limit=args.limit,
                catalog_path=args.catalog,
                class_name_to_id=class_map,
                label_map=label_map,
                force_split="train",
                skip_original_files=existing_originals,
                extra_meta={
                    "source_dataset": args.kaggle_ref,
                    "source_type": "kaggle_yolo",
                    "source_page_url": f"https://www.kaggle.com/datasets/{args.kaggle_ref}",
                    "source_license": audit.get("license") or "kaggle_dataset_license_unverified",
                    "license": audit.get("license") or "kaggle_dataset_license_unverified",
                    "source_author": args.kaggle_ref.split("/", 1)[0],
                    "phase19_kaggle_train_support": True,
                    "recognition_enabled": False,
                    "reviewed": True,
                    "needs_annotation": False,
                    "split_lock": True,
                },
            )
            import_result = {
                "attempted": True,
                "imported": imported,
                "existing_original_files": len(existing_originals),
                "resume": not args.no_resume,
            }

    report = {
        **audit,
        "import": import_result,
        "generated_at": datetime.now().isoformat(),
    }
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.catalog.exists():
        catalog = DatasetCatalog(args.catalog)
        try:
            report["catalog_source_counts"] = catalog.count_by_source()
        finally:
            catalog.close()
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def audit_kaggle_dataset(
    dataset: Path,
    kaggle_ref: str,
    source_name: str,
    label_map: dict[str, str],
) -> dict[str, Any]:
    if not dataset.exists():
        return {
            "dataset_path": str(dataset),
            "kaggle_ref": kaggle_ref,
            "source_name": source_name,
            "exists": False,
            "can_auto_import": False,
            "blocked_reason": "dataset_path_missing",
        }
    files = [path for path in dataset.rglob("*") if path.is_file()]
    suffix_counts = Counter(path.suffix.lower() or "<none>" for path in files)
    image_paths = [path for path in files if path.suffix.lower() in IMAGE_EXTS]
    label_paths = [
        path
        for path in files
        if path.suffix.lower() in LABEL_EXTS and path.parent.name.lower() == "labels"
    ]
    names = read_yolo_dataset_names(dataset)
    clean_names = {idx: name.strip() for idx, name in names.items()}
    mapped_names = {idx: (label_map.get(name, name)) for idx, name in clean_names.items()}
    unknown_mapped = sorted({name for name in mapped_names.values() if name not in TRAINING_CLASS_ORDER_45})
    kind = likely_dataset_kind(dataset, image_count=len(image_paths), label_count=len(label_paths))
    spec = KAGGLE_DATASETS.get(kaggle_ref)
    can_auto_import = kind == "yolo_detection" and bool(names) and not unknown_mapped
    blocked_reason = ""
    if kind != "yolo_detection":
        blocked_reason = "not_yolo_detection_needs_bbox_review"
    elif not names:
        blocked_reason = "missing_class_names"
    elif unknown_mapped:
        blocked_reason = "unmapped_class_names"
    return {
        "dataset_path": str(dataset),
        "kaggle_ref": kaggle_ref,
        "source_name": source_name,
        "expected_kind": spec.expected_kind if spec else "unknown",
        "exists": True,
        "file_count": len(files),
        "image_count": len(image_paths),
        "label_count": len(label_paths),
        "suffix_counts": dict(sorted(suffix_counts.items())),
        "class_names": clean_names,
        "mapped_class_names": mapped_names,
        "unknown_mapped_class_names": unknown_mapped,
        "kind": kind,
        "can_auto_import": can_auto_import,
        "blocked_reason": blocked_reason,
    }


def _existing_original_files(queue: Path, source: str) -> set[str]:
    values: set[str] = set()
    if not queue.exists():
        return values
    for meta_path in queue.glob("*.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(meta.get("source") or "") != source:
            continue
        original = str(meta.get("original_file") or "").strip()
        if not original:
            continue
        values.add(original)
        with suppress(OSError):
            values.add(str(Path(original).resolve()))
    return values


if __name__ == "__main__":
    raise SystemExit(main())
