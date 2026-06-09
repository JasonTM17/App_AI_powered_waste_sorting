"""Evaluate a candidate YOLO model and write a compact metrics JSON file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=Path("dataset_v2") / "yolo_trainset" / "data.yaml")
    parser.add_argument("--split", choices=["train", "val", "test"], default="test")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--max-det", type=int, default=100)
    parser.add_argument("--plots", action="store_true")
    parser.add_argument("--device", default="0")
    parser.add_argument("--out", type=Path, default=Path("runs") / "eval" / "metrics.json")
    args = parser.parse_args()

    if not args.model.exists():
        raise SystemExit(f"model not found: {args.model}")
    if not args.data.exists():
        raise SystemExit(f"data.yaml not found: {args.data}")

    from ultralytics import YOLO

    model = YOLO(str(args.model))
    metrics = model.val(
        data=str(args.data),
        split=args.split,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
        max_det=args.max_det,
        device=args.device,
        plots=args.plots,
    )
    report = {
        "model": str(args.model.resolve()),
        "data": str(args.data.resolve()),
        "split": args.split,
        "eval_config": {
            "imgsz": args.imgsz,
            "batch": args.batch,
            "workers": args.workers,
            "max_det": args.max_det,
            "plots": args.plots,
        },
        "metrics": _jsonable(getattr(metrics, "results_dict", {})),
        "per_class": _per_class_metrics(metrics),
        "save_dir": str(getattr(metrics, "save_dir", "")),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Evaluation written to {args.out}")
    return 0


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def _per_class_metrics(metrics: Any) -> dict[str, dict[str, float | int]]:
    box = getattr(metrics, "box", None)
    class_indexes = getattr(box, "ap_class_index", None)
    class_result = getattr(box, "class_result", None)
    names = getattr(metrics, "names", {})
    if box is None or class_indexes is None or not callable(class_result):
        return {}

    report: dict[str, dict[str, float | int]] = {}
    for result_index, raw_class_id in enumerate(class_indexes):
        class_id = int(raw_class_id)
        try:
            precision, recall, map50, map50_95 = class_result(result_index)
        except (IndexError, TypeError, ValueError):
            continue
        if isinstance(names, dict):
            class_name = str(names.get(class_id, class_id))
        else:
            class_name = str(names[class_id]) if class_id < len(names) else str(class_id)
        report[class_name] = {
            "class_id": class_id,
            "precision": float(precision),
            "recall": float(recall),
            "map50": float(map50),
            "map50_95": float(map50_95),
        }
    return report


if __name__ == "__main__":
    raise SystemExit(main())
