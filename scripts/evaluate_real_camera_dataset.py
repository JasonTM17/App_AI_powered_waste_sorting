"""Compare YOLO checkpoints on reviewed captures from the physical camera."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.dataset_trust import DatasetTrustState, classify_dataset_item  # noqa: E402
from app.core.weak_eval_audit import match_detections  # noqa: E402
from app.core.waste_categories import (  # noqa: E402
    TRAINING_CLASS_ORDER_45,
    canonical_class_name,
    category_for_class,
)

REAL_CAMERA_SOURCES = frozenset({"manual_camera_capture", "capture_session"})
EVALUABLE_STATES = frozenset({DatasetTrustState.TRAINABLE, DatasetTrustState.HOLDOUT})
BLURRY_MAX = 75.0
SOFT_MAX = 160.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, action="append", required=True)
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--out", type=Path, default=Path("runs/eval/real-camera-model-comparison.json"))
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.05)
    parser.add_argument(
        "--runtime-thresholds",
        action="store_true",
        help="Filter predictions with the persisted app model.conf_threshold/class_thresholds.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional app config path for --runtime-thresholds; defaults to AppData config.",
    )
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="0")
    args = parser.parse_args()

    samples, skipped = collect_samples(args.queue)
    if not samples:
        raise SystemExit("No reviewed real-camera samples were found.")
    report = {
        "queue": str(args.queue.resolve()),
        "note": "Camera-fit audit; most captures are training samples, not an unbiased holdout.",
        "sample_count": len(samples),
        "skipped": dict(skipped),
        "dataset": summarize_samples(samples),
        "runtime_thresholds": runtime_thresholds(args),
        "models": [evaluate_model(path, samples, args) for path in args.model],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Evaluated {len(samples)} reviewed camera captures across {len(args.model)} model(s).")
    print(f"Report: {args.out}")
    return 0


def collect_samples(queue: Path) -> tuple[list[dict[str, Any]], Counter[str]]:
    samples: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    for meta_path in sorted(queue.glob("*.json")):
        meta = _read_json(meta_path)
        if not meta:
            skipped["invalid_meta"] += 1
            continue
        if str(meta.get("source") or "") not in REAL_CAMERA_SOURCES:
            continue
        if meta.get("reviewed") is not True or meta.get("bbox_reviewed") is not True:
            skipped["not_reviewed"] += 1
            continue
        if meta.get("training_excluded") is True:
            skipped["training_excluded"] += 1
            continue
        decision = classify_dataset_item(meta)
        if decision.state not in EVALUABLE_STATES:
            skipped[f"trust:{decision.state.value}"] += 1
            continue
        image_path = meta_path.with_suffix(".jpg")
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            skipped["missing_image"] += 1
            continue
        boxes = _ground_truth(meta)
        if not boxes:
            skipped["no_valid_boxes"] += 1
            continue
        samples.append(
            {
                "image": str(image_path),
                "boxes": boxes,
                "source": str(meta.get("source")),
                "split": str(meta.get("split") or "unspecified"),
                "blur_score": _blur_score(image),
            }
        )
    return samples, skipped


def summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    classes: Counter[str] = Counter()
    blur: Counter[str] = Counter()
    splits: Counter[str] = Counter()
    for sample in samples:
        classes.update(str(box["class_name"]) for box in sample["boxes"])
        blur[blur_bucket(float(sample["blur_score"]))] += 1
        splits[str(sample["split"])] += 1
    missing = sorted(set(TRAINING_CLASS_ORDER_45) - set(classes))
    return {
        "class_boxes": dict(sorted(classes.items())),
        "represented_classes": len(classes),
        "missing_classes": missing,
        "blur_buckets": dict(blur),
        "splits": dict(splits),
    }


def evaluate_model(model_path: Path, samples: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    from ultralytics import YOLO

    model = YOLO(str(model_path.resolve()))
    model_names = {int(key): canonical_class_name(str(value)) for key, value in model.names.items()}
    thresholds = runtime_thresholds(args)
    predict_conf = min([float(args.conf), *thresholds.values()]) if thresholds else float(args.conf)
    focus = set(TRAINING_CLASS_ORDER_45)
    totals: dict[str, Counter[str]] = defaultdict(Counter)
    blur_totals: dict[str, Counter[str]] = defaultdict(Counter)
    route_totals: Counter[str] = Counter()
    route_confusions: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    for offset in range(0, len(samples), args.batch):
        batch = samples[offset : offset + args.batch]
        results = model.predict(
            source=[sample["image"] for sample in batch],
            imgsz=args.imgsz,
            conf=predict_conf,
            iou=0.7,
            device=args.device,
            verbose=False,
        )
        for sample, result in zip(batch, results, strict=True):
            predictions = _predictions(result, model_names, thresholds=thresholds)
            matched = match_detections(
                sample["boxes"], predictions, focus_classes=focus, iou_threshold=args.iou
            )
            route_eval = _route_eval(sample["boxes"], predictions, iou_threshold=args.iou)
            route_totals.update(route_eval["counts"])
            route_confusions.update(route_eval["confusions"])
            bucket = blur_bucket(float(sample["blur_score"]))
            for class_name, counts in matched["counts"].items():
                totals[class_name].update(counts)
                blur_totals[bucket].update({key: value for key, value in counts.items() if key in {"tp", "fp", "fn"}})
            for row in matched["failures"][:8]:
                failures.append({"image": sample["image"], "blur_bucket": bucket, **row})
    return {
        "model": str(model_path.resolve()),
        "thresholds": thresholds,
        "overall": _metrics(_sum_counts(totals.values())),
        "route_level": {
            "overall": _metrics(route_totals),
            "confusions": dict(route_confusions.most_common(20)),
        },
        "per_class": {name: _metrics(counts) for name, counts in sorted(totals.items())},
        "per_blur_bucket": {name: _metrics(counts) for name, counts in sorted(blur_totals.items())},
        "failure_examples": failures[:120],
    }


def runtime_thresholds(args: argparse.Namespace) -> dict[str, float]:
    if not bool(getattr(args, "runtime_thresholds", False)):
        return {}
    from app.core.config import load_config
    from app.utils.paths import config_path

    path = args.config or config_path()
    cfg = load_config(path)
    thresholds = {"*": float(cfg.model.conf_threshold)}
    thresholds.update({str(k): float(v) for k, v in cfg.model.class_thresholds.items()})
    return thresholds


def blur_bucket(score: float) -> str:
    if score < BLURRY_MAX:
        return "blurry_real_camera"
    if score < SOFT_MAX:
        return "soft_real_camera"
    return "sharp_real_camera"


def _metrics(counts: Counter[str]) -> dict[str, float | int]:
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(tp / max(1, tp + fp), 4),
        "recall": round(tp / max(1, tp + fn), 4),
        "f1": round((2 * tp) / max(1, 2 * tp + fp + fn), 4),
    }


def _sum_counts(values: Any) -> Counter[str]:
    total: Counter[str] = Counter()
    for counts in values:
        total.update({key: value for key, value in counts.items() if key in {"tp", "fp", "fn"}})
    return total


def _route_eval(
    gts: list[dict[str, Any]],
    preds: list[dict[str, Any]],
    *,
    iou_threshold: float,
) -> dict[str, Counter[str]]:
    counts: Counter[str] = Counter()
    confusions: Counter[str] = Counter()
    used_predictions: set[int] = set()
    for gt in gts:
        gt_route = category_for_class(str(gt["class_name"])).code
        best_index, best_iou, best_pred = _best_prediction(gt, preds, used_predictions)
        if best_pred is None or best_iou < iou_threshold:
            counts["fn"] += 1
            confusions[f"{gt_route}->missing"] += 1
            continue
        used_predictions.add(best_index)
        pred_route = category_for_class(str(best_pred["class_name"])).code
        if pred_route == gt_route:
            counts["tp"] += 1
        else:
            counts["fn"] += 1
            counts["fp"] += 1
            confusions[f"{gt_route}->{pred_route}"] += 1
    for index, pred in enumerate(preds):
        if index in used_predictions:
            continue
        pred_route = category_for_class(str(pred["class_name"])).code
        counts["fp"] += 1
        confusions[f"extra->{pred_route}"] += 1
    return {"counts": counts, "confusions": confusions}


def _best_prediction(
    gt: dict[str, Any],
    preds: list[dict[str, Any]],
    used_predictions: set[int],
) -> tuple[int, float, dict[str, Any] | None]:
    best_index = -1
    best_iou = 0.0
    best_pred = None
    gt_box = gt["xyxy"]
    for index, pred in enumerate(preds):
        if index in used_predictions:
            continue
        iou = _bbox_iou(gt_box, pred["xyxy"])
        if iou > best_iou:
            best_index = index
            best_iou = iou
            best_pred = pred
    return best_index, best_iou, best_pred


def _bbox_iou(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    intersection = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(
        0.0, min(ay2, by2) - max(ay1, by1)
    )
    first_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    second_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return intersection / max(first_area + second_area - intersection, 1.0)


def _ground_truth(meta: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for box in meta.get("boxes") or []:
        name = canonical_class_name(str(box.get("cls_name") or ""))
        xyxy = box.get("xyxy")
        if name in TRAINING_CLASS_ORDER_45 and isinstance(xyxy, list | tuple) and len(xyxy) >= 4:
            rows.append({"class_name": name, "xyxy": tuple(float(value) for value in xyxy[:4])})
    return rows


def _predictions(
    result: Any,
    names: dict[int, str],
    *,
    thresholds: dict[str, float],
) -> list[dict[str, Any]]:
    rows = []
    for box in getattr(result, "boxes", ()) or ():
        class_id = int(box.cls[0])
        class_name = names.get(class_id, str(class_id))
        confidence = float(box.conf[0])
        threshold = thresholds.get(class_name, thresholds.get("*", 0.0))
        if confidence < threshold:
            continue
        rows.append(
            {
                "class_name": class_name,
                "conf": confidence,
                "xyxy": tuple(float(value) for value in box.xyxy[0].tolist()),
            }
        )
    return rows


def _blur_score(image: Any) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


if __name__ == "__main__":
    raise SystemExit(main())
