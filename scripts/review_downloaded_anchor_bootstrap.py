"""Review downloaded bootstrap images with conservative tight bbox candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.phase18_anchor_tools import review_downloaded_bootstrap  # noqa: E402
from app.core.weak_recovery_filters import WHOLE_IMAGE_COVERAGE_THRESHOLD  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--catalog", type=Path, default=Path("dataset_v2/dataset.db"))
    parser.add_argument("--report", type=Path, default=Path("dataset_v2/phase18_downloaded_anchor_review_report.json"))
    parser.add_argument("--coverage-threshold", type=float, default=WHOLE_IMAGE_COVERAGE_THRESHOLD)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    report = review_downloaded_bootstrap(
        args.queue,
        catalog_path=args.catalog,
        dry_run=args.dry_run,
        threshold=args.coverage_threshold,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Downloaded bootstrap reviewed: {report['reviewed_total']}; skipped: {report['skipped']}")
    print(f"Report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
