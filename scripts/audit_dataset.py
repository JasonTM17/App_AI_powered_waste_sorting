"""Audit the local training queue and dataset catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.dataset_catalog import DatasetCatalog  # noqa: E402
from app.core.dataset_queue import summarize_queue  # noqa: E402
from app.utils.paths import dataset_db_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2") / "low_conf_queue")
    parser.add_argument("--db", type=Path, default=dataset_db_path())
    parser.add_argument("--rare-threshold", type=int, default=100)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
