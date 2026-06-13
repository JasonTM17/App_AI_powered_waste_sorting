"""Build Phase 20 manifest for Kaggle classification-only real images."""

from __future__ import annotations

import argparse
import json
import os
import sys
from itertools import chain
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.kaggle_real_image_pipeline import (  # noqa: E402
    DOMESTIC_SOLID_WASTE_REF,
    GARBAGE_CLASSIFICATION_V2_REF,
    VN_TRASH_CLASSIFICATION_REF,
    iter_classification_rows,
    write_manifest,
)

DEFAULT_KAGGLE_CACHE = ROOT / ".local" / "kagglehub-cache"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=default_kaggle_cache_root(),
        help="KaggleHub cache root. Defaults to .local/kagglehub-cache.",
    )
    parser.add_argument(
        "--vn-trash",
        type=Path,
    )
    parser.add_argument(
        "--domestic",
        type=Path,
    )
    parser.add_argument(
        "--garbage-v2",
        type=Path,
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("dataset_v2") / "phase20_kaggle_classification_manifest.jsonl",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("dataset_v2") / "phase20_kaggle_classification_manifest_summary.json",
    )
    args = parser.parse_args()

    cache_root = args.cache_root.expanduser().resolve()
    vn_trash = args.vn_trash or _dataset_version(
        cache_root, "mrgetshjtdone", "vn-trash-classification", 1
    )
    domestic = args.domestic or _dataset_version(
        cache_root, "thanhngnguyn", "vietnam-domestic-solid-waste", 2
    )
    garbage_versions = (
        cache_root / "datasets" / "sumn2u" / "garbage-classification-v2" / "versions"
    )
    garbage_v2 = (
        args.garbage_v2
        or _latest_existing_version(garbage_versions)
        or garbage_versions / "1"
    )

    sources = [
        (vn_trash, VN_TRASH_CLASSIFICATION_REF),
        (domestic, DOMESTIC_SOLID_WASTE_REF),
    ]
    if garbage_v2.exists():
        sources.append((garbage_v2, GARBAGE_CLASSIFICATION_V2_REF))
    rows = chain.from_iterable(iter_classification_rows(path, ref) for path, ref in sources)
    summary = write_manifest(rows, args.out, args.summary)
    summary["configured_sources"] = {ref: str(path) for path, ref in sources}
    summary["missing_sources"] = {
        GARBAGE_CLASSIFICATION_V2_REF: str(garbage_v2)
    } if not garbage_v2.exists() else {}
    args.summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def default_kaggle_cache_root() -> Path:
    configured = os.environ.get("TRASH_SORTER_KAGGLE_CACHE", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_KAGGLE_CACHE


def _dataset_version(cache_root: Path, owner: str, slug: str, version: int) -> Path:
    return cache_root / "datasets" / owner / slug / "versions" / str(version)


def _latest_existing_version(versions_dir: Path) -> Path | None:
    if not versions_dir.exists():
        return None
    versions: list[tuple[int, Path]] = []
    for path in versions_dir.iterdir():
        if not path.is_dir():
            continue
        try:
            versions.append((int(path.name), path))
        except ValueError:
            continue
    return max(versions, default=(0, None))[1]


if __name__ == "__main__":
    raise SystemExit(main())
