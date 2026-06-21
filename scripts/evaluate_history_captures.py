"""Evaluate the active YOLO model against preserved history captures.

Historical model labels are not ground truth. This read-only audit highlights
drift and review candidates without changing history.db or training metadata.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.waste_categories import canonical_class_name, category_for_class  # noqa: E402
from app.utils.paths import config_path, db_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=db_path())
    parser.add_argument("--model", type=Path)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("runs/eval/history-capture-model-audit.json"),
    )
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.05)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--device", default="0")
    args = parser.parse_args()

    model_path = (args.model or _configured_model_path()).expanduser().resolve()
    if not model_path.is_file():
        raise SystemExit(f"Model not found: {model_path}")
    rows = load_history_rows(args.db)
    if not rows:
        raise SystemExit("No preserved history captures were found.")

    from ultralytics import YOLO

    model = YOLO(str(model_path))
    names = {int(key): canonical_class_name(str(value)) for key, value in model.names.items()}
    results: list[dict[str, Any]] = []
    for offset in range(0, len(rows), max(1, args.batch)):
        batch = rows[offset : offset + max(1, args.batch)]
        predictions = model.predict(
            source=[row["image_path"] for row in batch],
            imgsz=args.imgsz,
            conf=args.conf,
            device=args.device,
            verbose=False,
        )
        for row, prediction in zip(batch, predictions, strict=True):
            candidates = _prediction_candidates(prediction, names)
            selected = select_prediction(candidates, row["bbox"])
            current_label = str(selected.get("class_name") or "Unknown object")
            current_conf = float(selected.get("confidence") or 0.0)
            old_label = canonical_class_name(str(row["old_label"]))
            old_route = _route(old_label)
            current_route = _route(current_label)
            exact_agreement = current_label == old_label
            route_agreement = bool(old_route and current_route and old_route == current_route)
            results.append(
                {
                    **row,
                    "current_label": current_label,
                    "current_confidence": round(current_conf, 6),
                    "current_bbox": selected.get("bbox"),
                    "candidate_count": len(candidates),
                    "exact_agreement": exact_agreement,
                    "route_agreement": route_agreement,
                    "old_route": old_route,
                    "current_route": current_route,
                    "review_required": (
                        not exact_agreement
                        or current_conf < 0.45
                        or current_label == "Unknown object"
                    ),
                }
            )

    report = build_report(args.db, model_path, results)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Report: {args.out.resolve()}")
    return 0


def load_history_rows(database: Path) -> list[dict[str, Any]]:
    source = database.expanduser().resolve()
    rows: list[dict[str, Any]] = []
    with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        for row in connection.execute(
            "select id, ts, cls_name, conf, bbox_x1, bbox_y1, bbox_x2, bbox_y2, "
            "image_path, label_status, display_label from detections order by id"
        ):
            image_path = Path(str(row["image_path"] or ""))
            if not image_path.is_file():
                continue
            image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            if image is None:
                continue
            rows.append(
                {
                    "history_id": int(row["id"]),
                    "timestamp": str(row["ts"] or ""),
                    "image_path": str(image_path),
                    "old_label": str(row["cls_name"] or "Unknown object"),
                    "old_confidence": round(float(row["conf"] or 0.0), 6),
                    "label_status": str(row["label_status"] or "unreviewed"),
                    "display_label": str(row["display_label"] or ""),
                    "bbox": _history_bbox(row),
                    "blur_score": round(float(cv2.Laplacian(image, cv2.CV_64F).var()), 3),
                }
            )
    return rows


def select_prediction(
    candidates: list[dict[str, Any]],
    history_bbox: list[float] | None,
) -> dict[str, Any]:
    if not candidates:
        return {}
    if history_bbox:
        return max(
            candidates,
            key=lambda item: (
                _iou(history_bbox, list(item["bbox"])),
                float(item["confidence"]),
            ),
        )
    return max(candidates, key=lambda item: float(item["confidence"]))


def build_report(database: Path, model_path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    confusions: Counter[str] = Counter()
    per_old_label: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        old_label = str(row["old_label"])
        current_label = str(row["current_label"])
        confusions[f"{old_label} -> {current_label}"] += 1
        per_old_label[old_label][current_label] += 1
    review_rows = [row for row in rows if row["review_required"]]
    return {
        "summary": {
            "database": str(database.expanduser().resolve()),
            "model": str(model_path),
            "capture_count": len(rows),
            "human_verified_count": sum(
                row["label_status"] == "human_verified" for row in rows
            ),
            "exact_agreement_count": sum(row["exact_agreement"] for row in rows),
            "route_agreement_count": sum(row["route_agreement"] for row in rows),
            "review_required_count": len(review_rows),
            "unknown_count": sum(row["current_label"] == "Unknown object" for row in rows),
            "note": "Old history labels are model output, not human ground truth.",
        },
        "confusions": dict(confusions.most_common()),
        "per_old_label": {
            label: dict(counter.most_common()) for label, counter in sorted(per_old_label.items())
        },
        "review_candidates": sorted(
            review_rows,
            key=lambda row: (float(row["current_confidence"]), int(row["history_id"])),
        ),
        "rows": rows,
    }


def _configured_model_path() -> Path:
    cfg = json.loads(config_path().read_text(encoding="utf-8"))
    raw_path = str(cfg.get("model", {}).get("path") or "")
    path = Path(raw_path)
    if path.is_absolute():
        return path
    project_candidate = Path.cwd() / path
    if project_candidate.is_file():
        return project_candidate
    bundled_candidate = Path(__file__).resolve().parent.parent / path
    return bundled_candidate


def _prediction_candidates(prediction: Any, names: dict[int, str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    boxes = getattr(prediction, "boxes", None)
    if boxes is None:
        return candidates
    for box in boxes:
        cls_id = int(box.cls[0].item())
        candidates.append(
            {
                "class_name": names.get(cls_id, str(cls_id)),
                "confidence": float(box.conf[0].item()),
                "bbox": [round(float(value), 3) for value in box.xyxy[0].tolist()],
            }
        )
    return candidates


def _history_bbox(row: sqlite3.Row) -> list[float] | None:
    values = [row["bbox_x1"], row["bbox_y1"], row["bbox_x2"], row["bbox_y2"]]
    if any(value is None for value in values):
        return None
    bbox = [float(value) for value in values]
    if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        return None
    return bbox


def _route(class_name: str) -> str:
    category = category_for_class(class_name)
    return str(category.code) if category is not None else ""


def _iou(left: list[float], right: list[float]) -> float:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[2], right[2])
    y2 = min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
