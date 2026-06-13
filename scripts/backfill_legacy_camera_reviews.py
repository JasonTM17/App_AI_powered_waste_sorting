"""Backfill bbox approval for camera samples reviewed by the legacy UI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.dataset_metadata_migrations import (  # noqa: E402
    backfill_legacy_camera_bbox_reviews,
)
from app.utils.paths import dataset_db_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2") / "low_conf_queue")
    parser.add_argument("--db", type=Path, default=dataset_db_path())
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    result = backfill_legacy_camera_bbox_reviews(
        args.queue,
        apply=args.apply,
        catalog_path=args.db,
    )
    action = "applied" if args.apply else "eligible"
    print(f"{action}={len(result.applied if args.apply else result.eligible)}")
    for path in result.applied if args.apply else result.eligible:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
