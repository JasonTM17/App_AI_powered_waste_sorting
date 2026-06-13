"""Audit the local training queue and dataset catalog."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.dataset_catalog import DatasetCatalog  # noqa: E402
from app.core.dataset_queue import (  # noqa: E402
    is_trainable_meta,
    is_trusted_meta,
    summarize_queue,
)
from app.core.dataset_trust import (  # noqa: E402
    DatasetTrustState,
    classify_dataset_item,
    is_holdout_meta,
)
from app.core.licensed_source_ingestion import source_manifest_issues  # noqa: E402
from app.core.source_quality_report import build_source_quality_report  # noqa: E402
from app.core.waste_categories import (  # noqa: E402
    TRAINING_CLASS_ORDER_45,
    canonical_class_name,
    category_for_class,
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
    parser.add_argument("--blocked-reasons", action="store_true")
    parser.add_argument("--deep-quality-scan", action="store_true")
    parser.add_argument("--quality-json", type=Path)
    args = parser.parse_args()

    queue_summary = summarize_queue(args.queue)
    include_quality = args.json or args.blocked_reasons or args.quality_json is not None
    blocked_reason_report = (
        _build_blocked_reason_report(args.queue, validate_image_bounds=args.deep_quality_scan)
        if include_quality
        else {}
    )
    fast_quality_tables = _build_fast_quality_tables(args.queue) if include_quality else {}
    source_quality = (
        build_source_quality_report(args.queue)
        if args.deep_quality_scan
        else _light_source_quality_report(args.queue, queue_summary, blocked_reason_report)
    )
    hard_negative_report = _build_hard_negative_report(args.queue)
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
    trainable_classes = dict(queue_summary.get("trainable_classes") or {})
    blocked_classes = dict(queue_summary.get("blocked_classes") or {})
    trainset = _read_yolo_data_yaml(args.trainset_data)
    trainset["alignment"] = _training_class_alignment(trainable_classes, trainset)
    trainset["catalog_alignment"] = _training_class_alignment(classes, trainset)
    trainset["integrity"] = _build_trainset_integrity_report(args.trainset_data, trainset)
    report = {
        "queue_dir": str(args.queue.resolve()),
        "catalog_path": str(args.db.resolve()),
        "queue_images": int(queue_summary["images"]),
        "queue_boxes": int(queue_summary["boxes"]),
        "catalog_total": catalog_total,
        "box_catalog_total": box_total,
        "class_catalog_total": class_total,
        "sources": sources,
        "trainable_classes": trainable_classes,
        "blocked_classes": blocked_classes,
        "missing_meta": int(queue_summary["missing_meta"]),
        "untrusted": int(queue_summary["untrusted"]),
        "rare_threshold": args.rare_threshold,
        "rare_classes": rare,
        "trainset": trainset,
        "blocked_reason_report": blocked_reason_report,
        "class_quality": fast_quality_tables.get("classes", {}),
        "source_gate_table": fast_quality_tables.get("sources", {}),
        "source_quality": source_quality,
        "hard_negative_report": hard_negative_report,
    }
    if args.quality_json is not None:
        args.quality_json.parent.mkdir(parents=True, exist_ok=True)
        args.quality_json.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
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
        print(f"Trainable box classes: {len(trainable_classes)}")
        print("Sources:")
        for source, count in sorted(sources.items()):
            print(f"  {source}: {count}")
        print(f"Rare classes (<{args.rare_threshold} boxes):")
        for name, count in rare.items():
            print(f"  {name}: {count}")
        if args.blocked_reasons:
            print("Blocked reasons:")
            for reason, count in blocked_reason_report["blocked_reasons"].items():
                print(f"  {reason}: {count}")
            print("Quality reasons:")
            for reason, count in blocked_reason_report["quality_reasons"].items():
                print(f"  {reason}: {count}")
        if hard_negative_report["total"]:
            print("Hard negatives:")
            print(f"  total: {hard_negative_report['total']}")
            print(f"  latest_ts: {hard_negative_report['latest_ts']}")
            for reason, count in hard_negative_report["by_reason"].items():
                print(f"  {reason}: {count}")
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
            print("  trainable classes outside training taxonomy:")
            for name in alignment["catalog_classes_not_in_training_order"]:
                print(f"    {name}")
        catalog_alignment = trainset["catalog_alignment"]
        if catalog_alignment["catalog_classes_not_in_training_order"]:
            print("  all catalog classes outside training taxonomy:")
            for name in catalog_alignment["catalog_classes_not_in_training_order"]:
                print(f"    {name}")
        if trainset["errors"]:
            print("  errors:")
            for error in trainset["errors"]:
                print(f"    {error}")
        integrity = trainset["integrity"]
        if integrity["exists"]:
            print("  integrity:")
            print(f"    images: {integrity['image_total']}")
            print(f"    labels: {integrity['label_total']}")
            print(f"    duplicate image groups: {integrity['duplicate_image_groups']}")
            print(
                "    cross-split duplicate groups: "
                f"{integrity['cross_split_duplicate_groups']}"
            )
            print(f"    missing label files: {integrity['missing_label_files']}")
            print(f"    invalid label lines: {integrity['invalid_label_lines']}")
    strict_failed = args.strict_trainset and not trainset["alignment"]["promotable_class_contract"]
    return 1 if strict_failed else 0


def _build_hard_negative_report(queue_dir: Path) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    expected: Counter[str] = Counter()
    latest_ts = ""
    images = sorted(queue_dir.glob("*.jpg")) if queue_dir.exists() else []
    for image_path in images:
        meta = _read_queue_meta(image_path)
        if not meta:
            continue
        if meta.get("hard_negative") is not True and str(meta.get("source") or "") != "hard_negative":
            continue
        reason = str(meta.get("hard_negative_reason") or "unknown")
        outcome = str(meta.get("expected_outcome") or "unknown")
        counts[reason] += 1
        expected[outcome] += 1
        ts = str(meta.get("ts") or "")
        if ts > latest_ts:
            latest_ts = ts
    return {
        "total": int(sum(counts.values())),
        "by_reason": dict(sorted(counts.items())),
        "by_expected_outcome": dict(sorted(expected.items())),
        "latest_ts": latest_ts,
    }


def _build_blocked_reason_report(
    queue_dir: Path,
    *,
    validate_image_bounds: bool = False,
) -> dict[str, Any]:
    blocked_counts: Counter[str] = Counter()
    quality_counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    total_items = 0
    trainable_by_current_rules = 0
    blocked_by_current_rules = 0
    items_with_blocking_reasons = 0

    images = sorted(queue_dir.glob("*.jpg")) if queue_dir.exists() else []
    for image_path in images:
        total_items += 1
        meta_path = image_path.with_suffix(".json")
        if not meta_path.exists():
            _add_reason(blocked_counts, examples, "missing_meta", image_path)
            blocked_by_current_rules += 1
            items_with_blocking_reasons += 1
            continue
        try:
            value = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _add_reason(blocked_counts, examples, "invalid_json", image_path)
            blocked_by_current_rules += 1
            items_with_blocking_reasons += 1
            continue
        if not isinstance(value, dict):
            _add_reason(blocked_counts, examples, "invalid_json", image_path)
            blocked_by_current_rules += 1
            items_with_blocking_reasons += 1
            continue

        meta = value
        if is_trainable_meta(meta):
            trainable_by_current_rules += 1
        else:
            blocked_by_current_rules += 1

        blocking_reasons = _blocking_reasons_for_meta(
            meta,
            image_path,
            validate_image_bounds=validate_image_bounds,
        )
        quality_reasons = _quality_reasons_for_meta(meta)
        if blocking_reasons:
            items_with_blocking_reasons += 1
        for reason in blocking_reasons:
            _add_reason(blocked_counts, examples, reason, image_path)
        for reason in quality_reasons:
            _add_reason(quality_counts, examples, reason, image_path)

    return {
        "total_items": total_items,
        "trainable_by_current_rules": trainable_by_current_rules,
        "blocked_by_current_rules": blocked_by_current_rules,
        "items_with_blocking_reasons": items_with_blocking_reasons,
        "blocked_reasons": dict(sorted(blocked_counts.items())),
        "quality_reasons": dict(sorted(quality_counts.items())),
        "examples": dict(sorted(examples.items())),
    }


def _blocking_reasons_for_meta(
    meta: dict[str, Any],
    image_path: Path,
    *,
    validate_image_bounds: bool,
) -> list[str]:
    decision = classify_dataset_item(meta)
    reasons = [reason for reason in decision.reasons if reason != "holdout_only"]

    boxes = meta.get("boxes") or []
    width, height = _image_size(image_path) if validate_image_bounds else (None, None)
    if validate_image_bounds:
        for box in boxes:
            if not isinstance(box, dict):
                reasons.append("invalid_bbox")
                continue
            if not _valid_bbox(box.get("xyxy"), width, height):
                reasons.append("invalid_bbox")
    if not is_trusted_meta(meta) and "untrusted_source" not in reasons and "unknown_labels" not in reasons:
        reasons.append("untrusted_meta")
    return sorted(set(reasons))


def _quality_reasons_for_meta(meta: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if is_holdout_meta(meta):
        reasons.append("holdout_only")
    if meta.get("generated") is True or str(meta.get("source_type") or "").lower() == "generated":
        reasons.append("generated")
    if meta.get("camera_blur_augmented") is True:
        reasons.append("camera_blur_augmented")
    if meta.get("needs_annotation") is True:
        reasons.append("needs_annotation")
    return sorted(set(reasons))


def _add_reason(
    counts: Counter[str],
    examples: dict[str, list[str]],
    reason: str,
    image_path: Path,
) -> None:
    counts[reason] += 1
    if len(examples[reason]) < 5:
        examples[reason].append(image_path.stem)


def _image_size(image_path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        with Image.open(image_path) as image:
            width, height = image.size
            return int(width), int(height)
    except Exception:
        return None, None


def _valid_bbox(xyxy: object, width: int | None, height: int | None) -> bool:
    if not isinstance(xyxy, list | tuple) or len(xyxy) < 4:
        return False
    try:
        x1, y1, x2, y2 = (float(value) for value in xyxy[:4])
    except (TypeError, ValueError):
        return False
    if x2 <= x1 or y2 <= y1:
        return False
    if width is not None and (x1 < 0 or x2 > width):
        return False
    return not (height is not None and (y1 < 0 or y2 > height))


def _light_source_quality_report(
    queue_dir: Path,
    queue_summary: dict[str, Any],
    blocked_reason_report: dict[str, Any],
) -> dict[str, Any]:
    blocked_reasons = blocked_reason_report.get("blocked_reasons") if blocked_reason_report else {}
    issue_counts = {
        "source_license_issue": int((blocked_reasons or {}).get("source_license_issue", 0)),
        "off_taxonomy": int((blocked_reasons or {}).get("off_taxonomy", 0)),
        "invalid_bbox": int((blocked_reasons or {}).get("invalid_bbox", 0)),
    }
    issue_counts = {key: value for key, value in issue_counts.items() if value}
    return {
        "queue_dir": str(queue_dir.resolve()),
        "total_images": int(queue_summary.get("images") or 0),
        "deep_scan": False,
        "duplicate_images": None,
        "blurry_images": None,
        "issue_counts": issue_counts,
        "sources": dict(queue_summary.get("sources") or {}),
        "note": "Set --deep-quality-scan to hash images and estimate blur.",
    }


def _build_fast_quality_tables(queue_dir: Path) -> dict[str, Any]:
    class_rows: dict[str, Counter[str]] = defaultdict(Counter)
    source_rows: dict[str, Counter[str]] = defaultdict(Counter)
    images = sorted(queue_dir.glob("*.jpg")) if queue_dir.exists() else []
    for image_path in images:
        meta = _read_queue_meta(image_path)
        source = str((meta or {}).get("source") or "unknown")
        source_row = source_rows[source]
        source_row["images"] += 1
        if meta is None:
            source_row["missing_or_invalid_meta"] += 1
            continue

        decision = classify_dataset_item(meta)
        trainable = decision.trainable
        reviewed = meta.get("reviewed") is True and meta.get("bbox_reviewed") is True
        holdout = decision.state is DatasetTrustState.HOLDOUT or is_holdout_meta(meta)
        needs_annotation = meta.get("needs_annotation") is True
        source_issues = source_manifest_issues(meta)
        if trainable:
            source_row["trainable_images"] += 1
        else:
            source_row["blocked_images"] += 1
        if reviewed:
            source_row["reviewed_images"] += 1
        if "review_required" in decision.reasons:
            source_row["review_required_images"] += 1
        if holdout:
            source_row["holdout_images"] += 1
        if needs_annotation:
            source_row["needs_annotation_images"] += 1
        if source_issues:
            source_row["source_issue_images"] += 1

        seen_classes: set[str] = set()
        for box in meta.get("boxes") or []:
            if not isinstance(box, dict):
                continue
            class_name = canonical_class_name(str(box.get("cls_name") or "")) or str(box.get("cls_name") or "?")
            row = class_rows[class_name]
            row["boxes"] += 1
            if trainable:
                row["trainable_boxes"] += 1
            else:
                row["blocked_boxes"] += 1
            seen_classes.add(class_name)
        for class_name in seen_classes:
            row = class_rows[class_name]
            row["images"] += 1
            row["reviewed_images"] += int(reviewed)
            row["holdout_images"] += int(holdout)
            row["needs_annotation_images"] += int(needs_annotation)
            row["source_issue_images"] += int(bool(source_issues))

    return {
        "classes": _counter_table(class_rows),
        "sources": _counter_table(source_rows),
    }


def _read_queue_meta(image_path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _counter_table(rows: dict[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {
        name: {key: int(value) for key, value in sorted(counter.items())}
        for name, counter in sorted(rows.items())
    }


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


def _build_trainset_integrity_report(
    yaml_path: Path,
    trainset_summary: dict[str, Any],
) -> dict[str, Any]:
    root = yaml_path.parent
    names = {
        int(cls_id): str(name)
        for cls_id, name in (trainset_summary.get("names") or {}).items()
    }
    report: dict[str, Any] = {
        "root": str(root.resolve()),
        "exists": yaml_path.exists() and root.exists(),
        "image_total": 0,
        "label_total": 0,
        "split_images": {"train": 0, "valid": 0, "test": 0},
        "split_labels": {"train": 0, "valid": 0, "test": 0},
        "missing_label_files": 0,
        "invalid_label_lines": 0,
        "route_boxes": {"O": 0, "R": 0, "I": 0},
        "split_route_boxes": {
            "train": {"O": 0, "R": 0, "I": 0},
            "valid": {"O": 0, "R": 0, "I": 0},
            "test": {"O": 0, "R": 0, "I": 0},
        },
        "duplicate_image_groups": 0,
        "duplicate_image_files": 0,
        "cross_split_duplicate_groups": 0,
        "cross_split_duplicate_files": 0,
        "duplicate_examples": [],
        "invalid_label_examples": [],
    }
    if not report["exists"]:
        return report

    by_hash: dict[str, list[dict[str, str]]] = defaultdict(list)
    for split in ("train", "valid", "test"):
        image_dir = root / "images" / split
        label_dir = root / "labels" / split
        image_paths = [
            path
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp")
            for path in image_dir.glob(ext)
        ]
        for image_path in sorted(image_paths):
            report["image_total"] += 1
            report["split_images"][split] += 1
            image_hash = _sha256_file(image_path)
            by_hash[image_hash].append(
                {
                    "split": split,
                    "path": str(image_path.relative_to(root)),
                }
            )
            label_path = label_dir / f"{image_path.stem}.txt"
            if not label_path.exists():
                report["missing_label_files"] += 1
                continue
            report["label_total"] += 1
            report["split_labels"][split] += 1
            _scan_yolo_label_file(label_path, split, names, report, root)

    duplicate_groups = [items for items in by_hash.values() if len(items) > 1]
    cross_split_groups = [
        items for items in duplicate_groups if len({item["split"] for item in items}) > 1
    ]
    report["duplicate_image_groups"] = len(duplicate_groups)
    report["duplicate_image_files"] = sum(len(items) for items in duplicate_groups)
    report["cross_split_duplicate_groups"] = len(cross_split_groups)
    report["cross_split_duplicate_files"] = sum(len(items) for items in cross_split_groups)
    report["duplicate_examples"] = cross_split_groups[:20]
    return report


def _scan_yolo_label_file(
    label_path: Path,
    split: str,
    names: dict[int, str],
    report: dict[str, Any],
    root: Path,
) -> None:
    try:
        lines = label_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        report["invalid_label_lines"] += 1
        _append_invalid_label_example(report, root, label_path, "read_error")
        return
    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            report["invalid_label_lines"] += 1
            _append_invalid_label_example(report, root, label_path, f"line_{line_no}:shape")
            continue
        try:
            cls_id = int(parts[0])
            cx, cy, width, height = (float(value) for value in parts[1:])
        except ValueError:
            report["invalid_label_lines"] += 1
            _append_invalid_label_example(report, root, label_path, f"line_{line_no}:parse")
            continue
        if cls_id not in names or not (0 <= cx <= 1 and 0 <= cy <= 1) or not (0 < width <= 1 and 0 < height <= 1):
            report["invalid_label_lines"] += 1
            _append_invalid_label_example(report, root, label_path, f"line_{line_no}:range")
            continue
        route = category_for_class(names[cls_id]).code
        report["route_boxes"][route] += 1
        report["split_route_boxes"][split][route] += 1


def _append_invalid_label_example(
    report: dict[str, Any],
    root: Path,
    label_path: Path,
    reason: str,
) -> None:
    if len(report["invalid_label_examples"]) >= 20:
        return
    try:
        rel_path = str(label_path.relative_to(root))
    except ValueError:
        rel_path = str(label_path)
    report["invalid_label_examples"].append({"path": rel_path, "reason": reason})


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
