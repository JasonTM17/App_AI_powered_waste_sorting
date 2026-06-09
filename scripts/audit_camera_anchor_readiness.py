"""Report Phase 18 real camera-anchor readiness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.phase18_anchor_tools import audit_camera_anchor_readiness  # noqa: E402
from app.core.weak_recovery_filters import WHOLE_IMAGE_COVERAGE_THRESHOLD  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--report", type=Path, default=Path("dataset_v2/phase18_camera_anchor_readiness.json"))
    parser.add_argument("--coverage-threshold", type=float, default=WHOLE_IMAGE_COVERAGE_THRESHOLD)
    parser.add_argument("--fail-if-missing", action="store_true")
    args = parser.parse_args()

    report = audit_camera_anchor_readiness(args.queue, threshold=args.coverage_threshold)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Train allowed: {report['train_allowed']}")
    print(f"Missing real anchors: {report['missing_anchor_targets']}")
    print(f"Report: {args.report}")
    return 2 if args.fail_if_missing and report["missing_anchor_targets"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
