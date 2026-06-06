"""Normalize queue metadata class IDs to match the model class order."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.dataset_catalog import DatasetCatalog  # noqa: E402
from app.utils.paths import dataset_db_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2") / "low_conf_queue")
    parser.add_argument("--model", type=Path, default=Path("models") / "best.pt")
    parser.add_argument("--catalog", type=Path, default=dataset_db_path())
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    class_names = _model_classes(args.model)
    if not class_names:
        print("Could not read model classes; aborting.")
        return 2
    report = normalize_queue_class_ids(args.queue, class_names, write=args.write)
    if args.write:
        catalog = DatasetCatalog(args.catalog)
        try:
            report["catalog_indexed"] = catalog.index_queue(args.queue)
        finally:
            catalog.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def normalize_queue_class_ids(
    queue_dir: Path,
    class_names: dict[int, str],
    *,
    write: bool,
) -> dict[str, Any]:
    name_to_id = {name: cls_id for cls_id, name in class_names.items()}
    report: dict[str, Any] = {
        "queue_dir": str(queue_dir),
        "write": write,
        "scanned_items": 0,
        "changed_items": 0,
        "changed_boxes": 0,
        "unknown_boxes": 0,
        "changes": {},
    }
    if not queue_dir.exists():
        return report
    changes: dict[str, int] = {}
    for meta_path in sorted(queue_dir.glob("*.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(meta, dict):
            continue
        report["scanned_items"] += 1
        item_changed = False
        for box in meta.get("boxes") or []:
            if not isinstance(box, dict):
                continue
            cls_name = str(box.get("cls_name") or "")
            expected_id = name_to_id.get(cls_name)
            if expected_id is None:
                report["unknown_boxes"] += 1
                continue
            current_id = _optional_int(box.get("cls_id"))
            if current_id != expected_id:
                changes[f"{cls_name}:{current_id}->{expected_id}"] = (
                    changes.get(f"{cls_name}:{current_id}->{expected_id}", 0) + 1
                )
                box["cls_id"] = expected_id
                report["changed_boxes"] += 1
                item_changed = True
        if item_changed:
            report["changed_items"] += 1
            if write:
                meta_path.write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
    report["changes"] = changes
    return report


def _optional_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _model_classes(model_path: Path) -> dict[int, str]:
    try:
        from ultralytics import YOLO

        return {int(k): str(v) for k, v in dict(YOLO(str(model_path)).names).items()}
    except Exception:
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
