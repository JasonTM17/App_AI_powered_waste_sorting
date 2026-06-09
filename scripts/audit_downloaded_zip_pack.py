"""Audit downloaded ZIP packs before any dataset import."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.downloaded_zip_intake import PHASE17_ZIP_NAMES, audit_downloaded_zip  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "zips",
        nargs="*",
        type=Path,
        help="ZIP files to audit. Defaults to the three Phase 17 downloads.",
    )
    parser.add_argument("--downloads", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--out", type=Path, default=Path("dataset_v2/phase17_downloaded_zip_audit.json"))
    args = parser.parse_args()

    targets = args.zips or [args.downloads / name for name in PHASE17_ZIP_NAMES]
    reports = [audit_downloaded_zip(path) for path in targets]
    output = {
        "generated_at": datetime.now().isoformat(),
        "policy": {
            "train_directly": False,
            "hardware": "deferred",
            "production_model_promote": False,
        },
        "reports": reports,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Audited {len(reports)} ZIP files")
    print(f"Report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
