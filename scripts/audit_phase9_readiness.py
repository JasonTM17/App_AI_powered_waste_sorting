"""Audit Phase 9 readiness before long strong training."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.licensed_source_ingestion import (  # noqa: E402
    STRONG_MIN_HOLDOUT,
    STRONG_MIN_REVIEWED,
)
from app.core.source_quality_report import build_source_quality_report  # noqa: E402
from app.core.vietnam_waste_targets import P0_CLASSES  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--out", type=Path, default=Path("dataset_v2/phase9_readiness_report.json"))
    parser.add_argument("--class-name", action="append", default=[])
    args = parser.parse_args()

    targets = tuple(args.class_name or P0_CLASSES)
    quality = build_source_quality_report(args.queue)
    rows = {str(row["class_name"]): row for row in quality["classes"]}
    class_reports = [_class_gate(rows.get(name, {"class_name": name})) for name in targets]
    passed = all(item["ready_for_strong_train"] for item in class_reports)
    report = {
        "passed": passed,
        "queue_dir": quality["queue_dir"],
        "targets": class_reports,
        "quality": {
            "invalid_source_images": quality["invalid_source_images"],
            "duplicate_images": quality["duplicate_images"],
            "blurry_images": quality["blurry_images"],
            "generated_images": quality["generated_images"],
            "augmented_images": quality.get("augmented_images", 0),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Phase 9 readiness: {'PASS' if passed else 'BLOCKED'}")
    print(f"Report: {args.out}")
    return 0 if passed else 2


def _class_gate(row: dict[str, object]) -> dict[str, object]:
    reviewed = int(row.get("reviewed_count") or 0)
    holdout = int(row.get("holdout_count") or 0)
    source_issues = int(row.get("source_issue_count") or 0)
    generated_over_cap = bool(row.get("generated_over_cap"))
    return {
        "class_name": row.get("class_name", ""),
        "priority": row.get("priority", "P0"),
        "reviewed_count": reviewed,
        "holdout_count": holdout,
        "generated_count": int(row.get("generated_count") or 0),
        "augmented_count": int(row.get("augmented_count") or 0),
        "source_issue_count": source_issues,
        "missing_reviewed": max(0, STRONG_MIN_REVIEWED - reviewed),
        "missing_holdout": max(0, STRONG_MIN_HOLDOUT - holdout),
        "ready_for_strong_train": (
            reviewed >= STRONG_MIN_REVIEWED
            and holdout >= STRONG_MIN_HOLDOUT
            and source_issues == 0
            and not generated_over_cap
        ),
    }


if __name__ == "__main__":
    raise SystemExit(main())
