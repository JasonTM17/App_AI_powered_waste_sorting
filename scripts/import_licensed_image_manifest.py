"""Import licensed image URLs from a reviewed manifest into the manual queue."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.dataset_queue import import_manual_image_urls  # noqa: E402
from app.core.licensed_source_ingestion import validate_manual_url_source  # noqa: E402
from app.core.waste_categories import default_class_id_for_name  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--catalog", type=Path, default=Path("dataset_v2/dataset.db"))
    parser.add_argument("--delay-seconds", type=float, default=1.25)
    args = parser.parse_args()

    items = _load_manifest_items(args.manifest)
    existing_source_urls = _existing_source_urls(args.queue)
    added = 0
    skipped: list[dict[str, str]] = []
    for index, item in enumerate(items):
        try:
            class_name = str(item.get("canonical_class") or item.get("cls_name") or "").strip()
            image_url = str(item.get("image_url") or item.get("source_url") or "").strip()
            if image_url in existing_source_urls:
                skipped.append({"index": str(index), "reason": "duplicate source_url already imported"})
                continue
            source_type = str(item.get("source_type") or "licensed_url").strip()
            generated = bool(item.get("generated")) or source_type == "generated"
            source_meta = validate_manual_url_source(
                class_name=class_name,
                source_url=image_url,
                source_page_url=str(item.get("source_page_url") or "").strip(),
                source_license=str(item.get("license") or item.get("source_license") or "").strip(),
                source_author=str(item.get("author") or item.get("source_author") or "").strip(),
                source_type=source_type,
                generated=generated,
            )
            class_id = default_class_id_for_name(str(source_meta["canonical_class"])) or 0
            added += import_manual_image_urls(
                [image_url],
                args.queue,
                str(source_meta["canonical_class"]),
                class_id,
                source_page_url=str(item.get("source_page_url") or "").strip(),
                source_license=str(source_meta["source_license"]),
                source_author=str(source_meta["source_author"]),
                source_type=str(source_meta["source_type"]),
                generated=bool(source_meta["generated"]),
                extra_meta=source_meta,
                catalog_path=args.catalog,
            )
            existing_source_urls.add(image_url)
        except Exception as exc:
            skipped.append({"index": str(index), "reason": str(exc)})
        if args.delay_seconds > 0 and index < len(items) - 1:
            time.sleep(args.delay_seconds)

    report = {"added": added, "skipped": skipped}
    report_path = args.queue.parent / "licensed_import_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Imported {added} licensed image(s). Skipped {len(skipped)}.")
    print(f"Report: {report_path}")
    return 0 if not skipped else 2


def _load_manifest_items(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("items", [])
    if not isinstance(value, list):
        raise SystemExit("Manifest must be a JSON list or an object with an items list.")
    return [item for item in value if isinstance(item, dict)]


def _existing_source_urls(queue_dir: Path) -> set[str]:
    urls: set[str] = set()
    if not queue_dir.exists():
        return urls
    for meta_path in queue_dir.glob("*.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(meta, dict):
            url = str(meta.get("source_url") or "").strip()
            if url:
                urls.add(url)
    return urls


if __name__ == "__main__":
    raise SystemExit(main())
