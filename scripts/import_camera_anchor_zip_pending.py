"""Import Phase 17 camera-anchor bootstrap ZIP as pending-review queue items."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.downloaded_zip_intake import import_camera_anchor_zip_pending  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "zip",
        nargs="?",
        type=Path,
        default=Path.home() / "Downloads" / "camera_anchor_recovery_dataset_v1.zip",
    )
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--catalog", type=Path, default=Path("dataset_v2/dataset.db"))
    parser.add_argument("--out", type=Path, default=Path("dataset_v2/phase17_camera_anchor_import_report.json"))
    args = parser.parse_args()

    report = import_camera_anchor_zip_pending(args.zip, args.queue, catalog_path=args.catalog)
    report["generated_at"] = datetime.now().isoformat()
    report["policy"] = {
        "reviewed": False,
        "needs_annotation": True,
        "training_excluded": True,
        "counts_as_real_anchor": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Imported {report['imported']} pending-review ZIP images")
    print(f"Report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
