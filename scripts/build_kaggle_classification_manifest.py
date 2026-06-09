"""Build Phase 20 manifest for Kaggle classification-only real images."""

from __future__ import annotations

import argparse
import json
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


def main() -> int:
    default_garbage_v2 = _latest_existing_version(
        Path(r"D:\PHAN LOAI RAC\kagglehub-cache\datasets\sumn2u\garbage-classification-v2\versions")
    ) or Path(r"D:\PHAN LOAI RAC\kagglehub-cache\datasets\sumn2u\garbage-classification-v2\versions\1")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vn-trash",
        type=Path,
        default=Path(r"D:\PHAN LOAI RAC\kagglehub-cache\datasets\mrgetshjtdone\vn-trash-classification\versions\1"),
    )
    parser.add_argument(
        "--domestic",
        type=Path,
        default=Path(
            r"D:\PHAN LOAI RAC\kagglehub-cache\datasets\thanhngnguyn\vietnam-domestic-solid-waste\versions\2"
        ),
    )
    parser.add_argument(
        "--garbage-v2",
        type=Path,
        default=default_garbage_v2,
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

    sources = [
        (args.vn_trash, VN_TRASH_CLASSIFICATION_REF),
        (args.domestic, DOMESTIC_SOLID_WASTE_REF),
    ]
    if args.garbage_v2.exists():
        sources.append((args.garbage_v2, GARBAGE_CLASSIFICATION_V2_REF))
    rows = chain.from_iterable(iter_classification_rows(path, ref) for path, ref in sources)
    summary = write_manifest(rows, args.out, args.summary)
    summary["configured_sources"] = {ref: str(path) for path, ref in sources}
    summary["missing_sources"] = {
        GARBAGE_CLASSIFICATION_V2_REF: str(args.garbage_v2)
    } if not args.garbage_v2.exists() else {}
    args.summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


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
