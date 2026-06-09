"""Import a Roboflow/YOLOv8 export into the app's data queue.

Usage:
  python scripts/import_roboflow_dataset.py --zip path/to/dataset.zip
  python scripts/import_roboflow_dataset.py --folder path/to/extracted/dataset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.waste_categories import DEFAULT_CLASS_ORDER  # noqa: E402
from app.utils.dataset_import import (  # noqa: E402
    import_yolo_dataset_to_queue,
    label_map_for_preset,
)
from app.utils.paths import dataset_db_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--zip", type=Path)
    source.add_argument("--folder", type=Path)
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2") / "low_conf_queue")
    parser.add_argument("--source-name", default="roboflow")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--label-map",
        choices=[
            "none",
            "waste_detection_2",
            "pen_hardware_downloads",
            "kaggle_vietnam_waste",
            "roboflow_3kelas_v1",
            "roboflow_wastebasket_can_bottle_v3",
        ],
        default="none",
        help="Optional safe label remapping preset for known public datasets.",
    )
    parser.add_argument(
        "--drop-unmapped-labels",
        action="store_true",
        help="Drop boxes not present in the selected label map instead of marking the image untrusted.",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("models") / "best.pt",
        help="Model used to remap matching labels to the current 42 class IDs.",
    )
    args = parser.parse_args()

    dataset_path = args.zip or args.folder
    class_map = _model_class_map(args.model)
    label_map = label_map_for_preset(args.label_map)
    imported = import_yolo_dataset_to_queue(
        dataset_path,
        args.queue,
        source_name=args.source_name,
        limit=args.limit,
        catalog_path=dataset_db_path(),
        class_name_to_id=class_map,
        label_map=label_map,
        drop_unmapped_labels=args.drop_unmapped_labels,
    )
    print(f"Imported {imported} images into {args.queue}")
    print(f"Indexed dataset records in {dataset_db_path()}")
    return 0


def _model_class_map(model_path: Path) -> dict[str, int] | None:
    if not model_path.exists():
        return None
    try:
        from ultralytics import YOLO

        names = dict(YOLO(str(model_path)).names)
    except Exception as e:
        print(f"Warning: could not inspect model classes: {e}")
        return None
    class_map = {str(name): int(cls_id) for cls_id, name in names.items()}
    next_id = max(class_map.values(), default=-1) + 1
    for name in DEFAULT_CLASS_ORDER:
        if name in class_map:
            continue
        class_map[name] = next_id
        next_id += 1
    return class_map
if __name__ == "__main__":
    raise SystemExit(main())
