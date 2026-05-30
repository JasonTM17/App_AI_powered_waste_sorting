"""Export hard-negative queue items as a safety evaluation pack."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def export_safety_eval_pack(queue_dir: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.jsonl"
    rows: list[dict[str, Any]] = []

    for image_path in sorted(queue_dir.glob("*.jpg")) if queue_dir.exists() else []:
        meta = _read_meta(image_path)
        if not _is_safety_eval_item(meta):
            continue
        out_image = images_dir / image_path.name
        shutil.copy2(image_path, out_image)
        rows.append(
            {
                "image": str(Path("images") / out_image.name),
                "source_image": str(image_path.resolve()),
                "meta_path": str(image_path.with_suffix(".json").resolve()),
                "reason": str(meta.get("hard_negative_reason") or "unknown"),
                "expected_outcome": str(meta.get("expected_outcome") or "no_dispatch"),
                "ts": str(meta.get("ts") or ""),
                "detection_context": list(meta.get("detection_context") or []),
            }
        )

    with manifest_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    by_reason: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    for row in rows:
        by_reason[row["reason"]] = by_reason.get(row["reason"], 0) + 1
        by_outcome[row["expected_outcome"]] = by_outcome.get(row["expected_outcome"], 0) + 1
    summary = {
        "queue_dir": str(queue_dir.resolve()),
        "output_dir": str(output_dir.resolve()),
        "manifest": str(manifest_path.resolve()),
        "total": len(rows),
        "by_reason": dict(sorted(by_reason.items())),
        "by_expected_outcome": dict(sorted(by_outcome.items())),
        "labels_written": False,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def _read_meta(image_path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _is_safety_eval_item(meta: dict[str, Any] | None) -> bool:
    if not meta:
        return False
    hard_negative = meta.get("hard_negative") is True or str(meta.get("source") or "") == "hard_negative"
    return hard_negative and meta.get("evaluation_enabled") is not False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2") / "low_conf_queue")
    parser.add_argument("--out", type=Path, default=Path("dataset_v2") / "safety_eval_pack")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    summary = export_safety_eval_pack(args.queue, args.out)
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"Safety eval images: {summary['total']}")
        print(f"Manifest: {summary['manifest']}")
        for reason, count in summary["by_reason"].items():
            print(f"  {reason}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
