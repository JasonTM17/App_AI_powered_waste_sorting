"""Build a Phase 9 licensed-image manifest for weak P0 classes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.licensed_manifest_sources import (  # noqa: E402
    class_counts,
    count_class,
    csv_rows,
    wikimedia_rows,
)
from app.core.vietnam_waste_targets import P0_CLASSES  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("dataset_v2/phase9_p0_licensed_manifest.json"))
    parser.add_argument("--per-class", type=int, default=40)
    parser.add_argument("--class-name", action="append", default=[])
    parser.add_argument("--verified-csv", type=Path, action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    items = _build_rows(tuple(args.class_name or P0_CLASSES), args.per_class, tuple(args.verified_csv))
    report = {"items": items, "count": len(items), "classes": class_counts(items)}
    if args.dry_run:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    if not items:
        print("No licensed image metadata found. Manifest was not written.")
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest: {args.out}")
    print(f"Items: {len(items)}")
    return 0


def _build_rows(classes: tuple[str, ...], per_class: int, verified_csv: tuple[Path, ...]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    for class_name in classes:
        for row in wikimedia_rows(class_name, per_class):
            image_url = str(row["image_url"])
            if image_url in seen_urls:
                continue
            items.append(row)
            seen_urls.add(image_url)
            if count_class(items, class_name) >= per_class:
                break
    for csv_path in verified_csv:
        for row in csv_rows(csv_path):
            image_url = str(row["image_url"])
            if image_url not in seen_urls:
                items.append(row)
                seen_urls.add(image_url)
    return items


if __name__ == "__main__":
    raise SystemExit(main())
