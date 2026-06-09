"""Build a licensed image manifest for the Vietnamese common-waste catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.common_waste_catalog import COMMON_WASTE_ITEMS, CommonWasteItem  # noqa: E402
from app.core.licensed_manifest_sources import (  # noqa: E402
    class_counts,
    count_class,
    csv_rows,
    wikimedia_rows_for_queries,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("dataset_v2/phase13_vietnam50_licensed_manifest.json"))
    parser.add_argument("--per-item", type=int, default=6)
    parser.add_argument("--per-class-cap", type=int, default=80)
    parser.add_argument("--label", action="append", default=[])
    parser.add_argument("--verified-csv", type=Path, action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    labels = {value.casefold() for value in args.label}
    items = [item for item in COMMON_WASTE_ITEMS if not labels or item.label.casefold() in labels]
    rows = _build_rows(tuple(items), args.per_item, args.per_class_cap, tuple(args.verified_csv))
    report = {
        "items": rows,
        "count": len(rows),
        "catalog_item_count": len(items),
        "classes": class_counts(rows),
    }
    if args.dry_run:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    if not rows:
        print("No licensed image metadata found. Manifest was not written.")
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest: {args.out}")
    print(f"Catalog items: {len(items)}")
    print(f"Images: {len(rows)}")
    return 0


def _build_rows(
    items: tuple[CommonWasteItem, ...],
    per_item: int,
    per_class_cap: int,
    verified_csv: tuple[Path, ...],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    for item in items:
        label = item.label
        canonical_class = item.canonical_class
        queries = _queries_for_item(item)
        remaining = max(0, min(per_item, per_class_cap - count_class(rows, canonical_class)))
        if remaining <= 0:
            continue
        for row in wikimedia_rows_for_queries(canonical_class, queries, remaining):
            image_url = str(row.get("image_url") or "")
            if image_url in seen_urls:
                continue
            row["vietnam_common_label"] = label
            row["vietnam_common_aliases"] = list(item.aliases)
            row["query_terms"] = list(queries)
            rows.append(row)
            seen_urls.add(image_url)
            if count_class(rows, canonical_class) >= per_class_cap:
                break
    for csv_path in verified_csv:
        for row in csv_rows(csv_path):
            image_url = str(row.get("image_url") or "")
            if image_url not in seen_urls:
                row["vietnam_common_label"] = row.get("vietnam_common_label") or ""
                rows.append(row)
                seen_urls.add(image_url)
    return rows


def _queries_for_item(item: CommonWasteItem) -> tuple[str, ...]:
    label = item.label
    canonical_class = item.canonical_class
    aliases = tuple(str(alias) for alias in item.aliases)
    seen: set[str] = set()
    queries: list[str] = []
    english_aliases = tuple(alias for alias in aliases if _looks_like_english(alias))
    vietnamese_aliases = tuple(alias for alias in aliases if alias not in english_aliases)
    for value in (*english_aliases, canonical_class, *vietnamese_aliases, label):
        clean = " ".join(value.replace("/", " ").split()).strip()
        if clean and clean.casefold() not in seen:
            seen.add(clean.casefold())
            queries.append(clean)
    return tuple(queries)


def _looks_like_english(value: str) -> bool:
    hints = (
        "bag",
        "banana",
        "battery",
        "beer",
        "blister",
        "bottle",
        "box",
        "can",
        "cap",
        "carton",
        "ceramic",
        "charger",
        "coffee",
        "cup",
        "electronic",
        "eggshell",
        "foil",
        "food",
        "fruit",
        "glass",
        "mask",
        "metal",
        "milk",
        "newspaper",
        "packaging",
        "paper",
        "peel",
        "pen",
        "plastic",
        "scrap",
        "snack",
        "spray",
        "styrofoam",
        "tea",
        "toothbrush",
        "vegetable",
        "waste",
        "wrap",
    )
    text = value.casefold()
    return any(hint in text for hint in hints)


if __name__ == "__main__":
    raise SystemExit(main())
