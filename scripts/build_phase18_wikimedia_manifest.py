"""Build Phase 18 licensed Wikimedia manifest for weak camera-anchor classes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.licensed_manifest_sources import (  # noqa: E402
    DEFAULT_QUERIES,
    class_counts,
    count_class,
    csv_rows,
    wikimedia_rows_for_queries,
)
from app.core.weak_eval_audit import PHASE16_FOCUS_CLASSES  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("dataset_v2/phase18_wikimedia_manifest.json"))
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--per-class", type=int, default=12)
    parser.add_argument("--class-name", action="append", default=[])
    parser.add_argument("--verified-csv", type=Path, action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    classes = tuple(args.class_name or PHASE16_FOCUS_CLASSES)
    rows = _build_rows(classes, args.per_class, tuple(args.verified_csv), _existing_source_urls(args.queue))
    report = {
        "items": rows,
        "count": len(rows),
        "classes": class_counts(rows),
        "policy": {
            "source": "wikimedia",
            "import_state": "pending_review",
            "counts_as_real_anchor": False,
            "train_directly": False,
        },
    }
    if args.dry_run:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest: {args.out}")
    print(f"Images: {len(rows)}")
    return 0 if rows else 2


def _build_rows(
    classes: tuple[str, ...],
    per_class: int,
    verified_csv: tuple[Path, ...],
    existing_urls: set[str] | None = None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen_urls: set[str] = set(existing_urls or set())
    for class_name in classes:
        queries = DEFAULT_QUERIES.get(class_name, (class_name,))
        search_target = max(per_class * 5, 30)
        for row in wikimedia_rows_for_queries(class_name, queries, search_target):
            image_url = str(row.get("image_url") or "")
            if not image_url or image_url in seen_urls:
                continue
            row["phase18_weak_class"] = True
            row["query_terms"] = list(queries)
            rows.append(row)
            seen_urls.add(image_url)
            if count_class(rows, class_name) >= per_class:
                break
    for csv_path in verified_csv:
        for row in csv_rows(csv_path):
            image_url = str(row.get("image_url") or "")
            if image_url and image_url not in seen_urls:
                row["phase18_weak_class"] = True
                rows.append(row)
                seen_urls.add(image_url)
    return rows


def _existing_source_urls(queue_dir: Path) -> set[str]:
    urls: set[str] = set()
    if not queue_dir.exists():
        return urls
    for meta_path in queue_dir.glob("*.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        url = str(meta.get("source_url") or "").strip() if isinstance(meta, dict) else ""
        if url:
            urls.add(url)
    return urls


if __name__ == "__main__":
    raise SystemExit(main())
