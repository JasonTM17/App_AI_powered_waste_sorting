"""Copy preserved history captures into the manual review queue.

The import is idempotent and never marks an item trainable. Historical and
current model labels remain suggestions until an Admin reviews image and bbox.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("runs/eval/history-capture-model-audit.json"),
    )
    parser.add_argument(
        "--queue",
        type=Path,
        default=Path("dataset_v2/low_conf_queue"),
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    report = json.loads(args.audit.read_text(encoding="utf-8"))
    rows = list(report.get("rows") or [])
    planned = 0
    created = 0
    existing = 0
    missing = 0
    for row in rows:
        source = Path(str(row.get("image_path") or ""))
        if not source.is_file():
            missing += 1
            continue
        planned += 1
        stem = f"history_recovery_{int(row['history_id']):06d}"
        image_target = args.queue / f"{stem}.jpg"
        meta_target = args.queue / f"{stem}.json"
        if image_target.is_file() and meta_target.is_file():
            existing += 1
            continue
        if not args.apply:
            continue
        args.queue.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, image_target)
        meta_target.write_text(
            json.dumps(build_metadata(row, source), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        created += 1

    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "dry-run",
                "planned": planned,
                "created": created,
                "existing": existing,
                "missing": missing,
                "queue": str(args.queue.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


def build_metadata(row: dict[str, Any], source: Path) -> dict[str, Any]:
    current_label = str(row.get("current_label") or "Unknown object")
    current_confidence = float(row.get("current_confidence") or 0.0)
    exact_agreement = bool(row.get("exact_agreement"))
    review_required = bool(row.get("review_required", True))
    bbox = row.get("current_bbox") or row.get("bbox")
    boxes = []
    if isinstance(bbox, list) and len(bbox) == 4:
        boxes.append(
            {
                "cls_id": -1,
                "cls_name": current_label,
                "conf": current_confidence,
                "xyxy": [float(value) for value in bbox],
                "operator_label": "",
            }
        )
    return {
        "ts": datetime.now().astimezone().isoformat(),
        "source": "auto_review_queue",
        "origin_source": "history_capture_recovery",
        "history_id": int(row["history_id"]),
        "original_path": str(source.resolve()),
        "queue_reason": (
            "history_model_disagreement" if review_required else "history_unreviewed"
        ),
        "review_priority": "high" if review_required else "medium",
        "old_model_label": str(row.get("old_label") or ""),
        "old_model_confidence": float(row.get("old_confidence") or 0.0),
        "current_model_label": current_label,
        "current_model_confidence": current_confidence,
        "suggested_label": current_label if exact_agreement and current_confidence >= 0.45 else "",
        "blur_score": float(row.get("blur_score") or 0.0),
        "object_signature": f"history:{int(row['history_id'])}",
        "capture_session_id": f"history:{str(row.get('timestamp') or '')[:10]}",
        "is_screenshot_audit": False,
        "reviewed": False,
        "bbox_reviewed": False,
        "recognition_enabled": False,
        "trusted": False,
        "training_excluded": True,
        "needs_annotation": True,
        "boxes": boxes,
    }


if __name__ == "__main__":
    raise SystemExit(main())
