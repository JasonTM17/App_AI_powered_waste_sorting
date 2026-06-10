"""Audit the local training queue and dataset catalog."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.dataset_catalog import DatasetCatalog  # noqa: E402
from app.core.dataset_queue import summarize_queue  # noqa: E402
from app.core.waste_categories import (  # noqa: E402
    TRAINING_CLASS_ORDER_45,
    canonical_class_name,
)
from app.utils.paths import dataset_db_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2") / "low_conf_queue")
    parser.add_argument("--db", type=Path, default=dataset_db_path())
    parser.add_argument("--rare-threshold", type=int, default=100)
    parser.add_argument(
        "--trainset-data",
        type=Path,
        default=Path("dataset_v2") / "yolo_trainset" / "data.yaml",
    )
    parser.add_argument("--strict-trainset", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    queue_summary = summarize_queue(args.queue)
    catalog = DatasetCatalog(args.db)
    try:
        catalog_total = catalog.count_total()
        box_total = catalog.count_boxes_total()
        class_total = catalog.count_distinct_box_classes()
        sources = catalog.count_by_source()
        classes = catalog.count_box_classes() or dict(queue_summary["classes"])
    finally:
        catalog.close()

    rare = {
        name: count
        for name, count in sorted(classes.items(), key=lambda item: item[1])
        if count < args.rare_threshold
    }
    trainset = _read_yolo_data_yaml(args.trainset_data)
    trainset["alignment"] = _training_class_alignment(classes, trainset)
    report = {
        "queue_dir": str(args.queue.resolve()),
        "catalog_path": str(args.db.resolve()),
        "queue_images": int(queue_summary["images"]),
        "queue_boxes": int(queue_summary["boxes"]),
        "catalog_total": catalog_total,
        "box_catalog_total": box_total,
        "class_catalog_total": class_total,
        "sources": sources,
        "missing_meta": int(queue_summary["missing_meta"]),
        "untrusted": int(queue_summary["untrusted"]),
        "rare_threshold": args.rare_threshold,
        "rare_classes": rare,
        "trainset": trainset,
    }
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Queue images: {report['queue_images']}")
        print(f"Queue boxes: {report['queue_boxes']}")
        print(f"Catalog records: {catalog_total}")
        print(f"Box records: {box_total}")
        print(f"Classes: {class_total}")
        print(f"Missing meta: {report['missing_meta']}")
        print(f"Untrusted items: {report['untrusted']}")
        print("Sources:")
        for source, count in sorted(sources.items()):
            print(f"  {source}: {count}")
        print(f"Rare classes (<{args.rare_threshold} boxes):")
        for name, count in rare.items():
            print(f"  {name}: {count}")
        alignment = trainset["alignment"]
        print("Trainset contract:")
        print(f"  data.yaml: {trainset['path']}")
        print(f"  exists: {trainset['exists']}")
        print(f"  declared nc: {trainset['nc']}")
        print(f"  parsed names: {trainset['class_total']}")
        print(f"  fixed 45-class order: {alignment['matches_training_order']}")
        if alignment["catalog_classes_not_in_trainset"]:
            print("  catalog classes not in trainset:")
            for name in alignment["catalog_classes_not_in_trainset"]:
                print(f"    {name}")
        if alignment["catalog_classes_not_in_training_order"]:
            print("  catalog classes outside training taxonomy:")
            for name in alignment["catalog_classes_not_in_training_order"]:
                print(f"    {name}")
        if trainset["errors"]:
            print("  errors:")
            for error in trainset["errors"]:
                print(f"    {error}")
    strict_failed = args.strict_trainset and not trainset["alignment"]["promotable_class_contract"]
    return 1 if strict_failed else 0


def _read_yolo_data_yaml(yaml_path: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": str(yaml_path.resolve()),
        "exists": yaml_path.exists(),
        "nc": 0,
        "class_total": 0,
        "names": {},
        "errors": [],
    }
    if not yaml_path.exists():
        summary["errors"].append("data.yaml not found")
        return summary

    names: dict[int, str] = {}
    in_names = False
    for raw_line in yaml_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("nc:"):
            try:
                summary["nc"] = int(line.split(":", 1)[1].strip())
            except ValueError:
                summary["errors"].append(f"invalid nc line: {line}")
            continue
        if line.startswith("names:"):
            in_names = True
            inline = line.split(":", 1)[1].strip()
            if inline:
                names.update(_parse_inline_names(inline, summary["errors"]))
                in_names = False
            continue
        if not in_names:
            continue
        if not raw_line.startswith((" ", "\t")):
            in_names = False
            continue
        if ":" not in line:
            summary["errors"].append(f"invalid names entry: {line}")
            continue
        raw_key, raw_value = line.split(":", 1)
        try:
            key = int(raw_key.strip())
        except ValueError:
            summary["errors"].append(f"invalid class id: {raw_key.strip()}")
            continue
        names[key] = raw_value.strip().strip("\"'")

    summary["names"] = names
    summary["class_total"] = len(names)
    if summary["nc"] and summary["nc"] != len(names):
        summary["errors"].append(f"nc={summary['nc']} but parsed {len(names)} names")
    return summary


def _parse_inline_names(value: str, errors: list[str]) -> dict[int, str]:
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        errors.append("could not parse inline names")
        return {}
    if isinstance(parsed, list | tuple):
        return {idx: str(name) for idx, name in enumerate(parsed)}
    if isinstance(parsed, dict):
        out: dict[int, str] = {}
        for key, name in parsed.items():
            try:
                out[int(key)] = str(name)
            except (TypeError, ValueError):
                errors.append(f"invalid inline class id: {key}")
        return out
    errors.append("inline names must be a list or dict")
    return {}


def _training_class_alignment(
    observed_classes: dict[str, int],
    trainset_summary: dict[str, Any],
) -> dict[str, Any]:
    trainset_names = {str(name) for name in trainset_summary.get("names", {}).values()}
    expected_by_id = dict(enumerate(TRAINING_CLASS_ORDER_45))
    expected_names = set(TRAINING_CLASS_ORDER_45)
    name_mismatches = {
        str(idx): {"expected": expected, "actual": trainset_summary.get("names", {}).get(idx)}
        for idx, expected in expected_by_id.items()
        if trainset_summary.get("names", {}).get(idx) != expected
    }
    observed_canonical = {
        canonical_class_name(name)
        for name, count in observed_classes.items()
        if int(count) > 0 and canonical_class_name(name)
    }
    catalog_classes_not_in_trainset = sorted(observed_canonical - trainset_names)
    catalog_classes_not_in_training_order = sorted(observed_canonical - expected_names)
    missing_expected_classes = sorted(expected_names - trainset_names)
    unknown_trainset_classes = sorted(trainset_names - expected_names)
    class_count_mismatch = (
        int(trainset_summary.get("nc") or 0) != len(trainset_summary.get("names", {}))
        or len(trainset_summary.get("names", {})) != len(TRAINING_CLASS_ORDER_45)
    )
    matches_training_order = (
        bool(trainset_summary.get("exists"))
        and not class_count_mismatch
        and not name_mismatches
        and not missing_expected_classes
        and not unknown_trainset_classes
    )
    return {
        "expected_class_total": len(TRAINING_CLASS_ORDER_45),
        "class_count_mismatch": class_count_mismatch,
        "matches_training_order": matches_training_order,
        "name_mismatches": name_mismatches,
        "missing_expected_classes": missing_expected_classes,
        "unknown_trainset_classes": unknown_trainset_classes,
        "catalog_classes_not_in_trainset": catalog_classes_not_in_trainset,
        "catalog_classes_not_in_training_order": catalog_classes_not_in_training_order,
        "promotable_class_contract": matches_training_order
        and not catalog_classes_not_in_training_order,
    }


if __name__ == "__main__":
    raise SystemExit(main())
