"""Audit and quarantine noisy whole-image licensed web reviews."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.dataset_catalog import DatasetCatalog  # noqa: E402
from app.core.dataset_queue import is_trainable_meta  # noqa: E402
from app.core.vietnam_waste_targets import P0_CLASSES  # noqa: E402
from app.core.waste_categories import canonical_class_name  # noqa: E402

ASSISTED_REVIEW_METHODS = {"phase12_assisted_review", "phase13_assisted_review"}
QUARANTINE_REASON = "phase14_whole_image_assisted_web_review"


def audit_web_reviews(
    queue_dir: Path,
    *,
    coverage_threshold: float = 0.92,
    quarantine: bool = False,
    catalog_path: Path | None = None,
    class_names: tuple[str, ...] = (),
    report_path: Path | None = None,
) -> dict[str, Any]:
    class_filter = {canonical_class_name(name) for name in class_names if name}
    catalog = DatasetCatalog(catalog_path) if catalog_path and quarantine else None
    totals: Counter[str] = Counter()
    by_class: dict[str, Counter[str]] = {}
    flagged_samples: list[dict[str, Any]] = []
    try:
        for image_path in sorted(queue_dir.glob("manual_web_*.jpg")):
            meta_path = image_path.with_suffix(".json")
            meta = _read_meta(meta_path)
            if not _is_reviewed_web(meta):
                continue
            classes = _classes_from_meta(meta)
            if class_filter and not classes.intersection(class_filter):
                continue
            width, height = _image_size(image_path)
            max_coverage = _max_box_coverage(meta, width, height)
            whole_image = max_coverage >= coverage_threshold
            assisted = str(meta.get("review_method") or "") in ASSISTED_REVIEW_METHODS
            explicitly_allowed = bool(
                meta.get("whole_image_allowed")
                or meta.get("whole_image_ok")
                or meta.get("single_object_product_photo")
            )
            risky = assisted and whole_image and not explicitly_allowed
            trainable_before = is_trainable_meta(meta)
            totals.update(_item_total_keys(meta, risky, whole_image, quarantine))
            for class_name in classes:
                row = by_class.setdefault(class_name, Counter())
                row.update(_item_total_keys(meta, risky, whole_image, quarantine))
                row["weak_p0"] += int(class_name in P0_CLASSES)
            if risky:
                sample = _sample_row(image_path, meta, classes, max_coverage, trainable_before)
                flagged_samples.append(sample)
                if quarantine:
                    _quarantine_meta(meta_path, meta, catalog, image_path)
    finally:
        if catalog is not None:
            catalog.close()

    report = {
        "queue_dir": str(queue_dir.resolve()),
        "coverage_threshold": coverage_threshold,
        "quarantine": quarantine,
        "generated_at": datetime.now().isoformat(),
        "totals": dict(totals),
        "classes": {name: dict(counts) for name, counts in sorted(by_class.items())},
        "flagged_samples": flagged_samples[:200],
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _item_total_keys(meta: dict[str, Any], risky: bool, whole_image: bool, quarantine: bool) -> Counter[str]:
    return Counter(
        {
            "reviewed_web": 1,
            "trainable_before": int(is_trainable_meta(meta)),
            "assisted_review": int(str(meta.get("review_method") or "") in ASSISTED_REVIEW_METHODS),
            "whole_image_bbox": int(whole_image),
            "flagged": int(risky),
            "quarantined": int(risky and quarantine),
        }
    )


def _quarantine_meta(
    meta_path: Path,
    meta: dict[str, Any],
    catalog: DatasetCatalog | None,
    image_path: Path,
) -> None:
    meta["training_excluded"] = True
    meta["recognition_enabled"] = False
    meta["needs_annotation"] = True
    meta["phase14_quarantined"] = True
    meta["training_exclusion_reason"] = QUARANTINE_REASON
    meta["quarantined_at"] = datetime.now().isoformat()
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    if catalog is not None:
        catalog.upsert_item(image_path, meta)


def _sample_row(
    image_path: Path,
    meta: dict[str, Any],
    classes: set[str],
    max_coverage: float,
    trainable_before: bool,
) -> dict[str, Any]:
    return {
        "image": str(image_path),
        "classes": sorted(classes),
        "max_bbox_coverage": round(max_coverage, 4),
        "review_method": meta.get("review_method", ""),
        "source_type": meta.get("source_type", ""),
        "split": meta.get("split", ""),
        "holdout": bool(meta.get("holdout")),
        "trainable_before": trainable_before,
        "source_page_url": meta.get("source_page_url", ""),
        "license": meta.get("license") or meta.get("source_license", ""),
        "author": meta.get("source_author", ""),
    }


def _classes_from_meta(meta: dict[str, Any]) -> set[str]:
    classes = set()
    for box in meta.get("boxes") or []:
        if isinstance(box, dict):
            class_name = canonical_class_name(str(box.get("cls_name") or ""))
            if class_name:
                classes.add(class_name)
    return classes


def _max_box_coverage(meta: dict[str, Any], width: int, height: int) -> float:
    image_area = max(1.0, float(width * height))
    coverages = []
    for box in meta.get("boxes") or []:
        xyxy = box.get("xyxy") if isinstance(box, dict) else None
        if not xyxy or len(xyxy) < 4:
            continue
        x1, y1, x2, y2 = (float(value) for value in xyxy[:4])
        bw = max(0.0, min(float(width), x2) - max(0.0, x1))
        bh = max(0.0, min(float(height), y2) - max(0.0, y1))
        coverages.append((bw * bh) / image_area)
    return max(coverages, default=0.0)


def _is_reviewed_web(meta: dict[str, Any]) -> bool:
    return (
        str(meta.get("source") or "") == "manual_web_import"
        and meta.get("reviewed") is True
        and meta.get("bbox_reviewed") is True
    )


def _read_meta(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _image_size(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            return image.size
    except OSError:
        return (1, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--catalog", type=Path, default=Path("dataset_v2/dataset.db"))
    parser.add_argument("--report", type=Path, default=Path("dataset_v2/phase14_web_review_quality_report.json"))
    parser.add_argument("--coverage-threshold", type=float, default=0.92)
    parser.add_argument("--class-name", action="append", default=[])
    parser.add_argument("--quarantine", action="store_true")
    args = parser.parse_args()

    report = audit_web_reviews(
        args.queue,
        coverage_threshold=args.coverage_threshold,
        quarantine=args.quarantine,
        catalog_path=args.catalog,
        class_names=tuple(args.class_name),
        report_path=args.report,
    )
    totals = report["totals"]
    print(
        "Web audit: "
        f"{totals.get('reviewed_web', 0)} reviewed web, "
        f"{totals.get('flagged', 0)} flagged, "
        f"{totals.get('quarantined', 0)} quarantined"
    )
    print(f"Report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
