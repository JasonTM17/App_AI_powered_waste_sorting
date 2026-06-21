"""Promote explicitly confirmed auto-review frames into recognition-only references."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from app.core.waste_categories import default_class_id_for_name


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue-dir", type=Path, required=True)
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--class-name", required=True)
    parser.add_argument("--operator-label", required=True)
    parser.add_argument("--reviewed-by", default="user_confirmation")
    parser.add_argument("--apply", action="store_true")
    return parser


def _best_source_box(meta: dict, class_name: str) -> list[int]:
    boxes = [box for box in meta.get("boxes") or [] if box.get("cls_name") == class_name]
    if not boxes:
        boxes = list(meta.get("boxes") or [])
    if not boxes:
        raise ValueError("source metadata contains no bounding box")
    best = max(
        boxes,
        key=lambda box: max(0, box["xyxy"][2] - box["xyxy"][0])
        * max(0, box["xyxy"][3] - box["xyxy"][1]),
    )
    return [round(float(value)) for value in best["xyxy"]]


def promote(
    queue_dir: Path,
    source_stems: list[str],
    *,
    class_name: str,
    operator_label: str,
    reviewed_by: str,
    apply: bool,
) -> list[dict[str, str]]:
    class_id = default_class_id_for_name(class_name)
    if class_id is None:
        raise ValueError(f"unknown canonical class: {class_name}")
    results: list[dict[str, str]] = []
    for source_stem in source_stems:
        source_image = queue_dir / f"{source_stem}.jpg"
        source_meta = queue_dir / f"{source_stem}.json"
        if not source_image.is_file() or not source_meta.is_file():
            raise FileNotFoundError(f"missing source pair: {source_stem}")
        meta = json.loads(source_meta.read_text(encoding="utf-8"))
        target_stem = f"manual_confirmed_{source_stem.removeprefix('auto_review_')}"
        target_image = queue_dir / f"{target_stem}.jpg"
        target_meta = queue_dir / f"{target_stem}.json"
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "source": "manual_camera_capture",
            "reviewed": True,
            "bbox_reviewed": True,
            "reviewed_by": reviewed_by,
            "reviewed_at": datetime.now(UTC).isoformat(),
            "needs_annotation": False,
            "recognition_enabled": True,
            "recognition_only": True,
            "training_excluded": True,
            "training_exclusion_reason": "recognition_only_user_confirmed",
            "derived_from": source_stem,
            "source_object_signature": meta.get("object_signature"),
            "source_session_id": meta.get("session_id"),
            "boxes": [
                {
                    "cls_id": class_id,
                    "cls_name": class_name,
                    "operator_label": operator_label,
                    "conf": 1.0,
                    "xyxy": _best_source_box(meta, class_name),
                }
            ],
        }
        results.append({"source": str(source_image), "target": str(target_image)})
        if apply:
            shutil.copy2(source_image, target_image)
            target_meta.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    return results


def main() -> int:
    args = _parser().parse_args()
    results = promote(
        args.queue_dir,
        args.source,
        class_name=args.class_name,
        operator_label=args.operator_label,
        reviewed_by=args.reviewed_by,
        apply=args.apply,
    )
    print(json.dumps({"applied": args.apply, "items": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
