"""Weak-class YOLO evaluation helpers for camera-anchor recovery."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.core.downloaded_zip_intake import DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE
from app.core.kaggle_intake import KAGGLE_TRAIN_SUPPORT_SOURCES
from app.core.waste_categories import TRAINING_CLASS_ORDER_45

PHASE16_REQUIRED_RECALL_CLASSES = ("Disposable tableware", "Ceramic", "Electronics")
PHASE16_FOCUS_CLASSES = (
    "Pen",
    "Disposable tableware",
    "Ceramic",
    "Unknown plastic",
    "Electronics",
)
PHASE16_ANCHOR_TARGETS = {
    "Disposable tableware": 30,
    "Ceramic": 25,
    "Electronics": 25,
    "Unknown plastic": 30,
    "Pen": 10,
}
REAL_ANCHOR_SOURCES = {"manual_camera_capture", "manual_import", "manual_phone_import", "capture_session"}
WEB_SOURCE = "manual_web_import"
TRAIN_SUPPORT_SOURCES = {WEB_SOURCE, DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE, *KAGGLE_TRAIN_SUPPORT_SOURCES}


def bbox_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return inter / max(area_a + area_b - inter, 1.0)


def match_detections(
    gts: list[dict[str, Any]],
    preds: list[dict[str, Any]],
    *,
    focus_classes: set[str],
    iou_threshold: float = 0.5,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    matched_pred_indexes: set[int] = set()
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for gt in gts:
        gt_class = str(gt["class_name"])
        if gt_class not in focus_classes:
            continue
        best_index, best_iou, best_pred = _best_prediction(gt, preds, matched_pred_indexes)
        if best_pred is not None and best_iou >= iou_threshold and best_pred["class_name"] == gt_class:
            matched_pred_indexes.add(best_index)
            counts[gt_class]["tp"] += 1
            continue
        counts[gt_class]["fn"] += 1
        confusion = str(best_pred["class_name"]) if best_pred is not None and best_iou >= iou_threshold else ""
        if confusion:
            counts[gt_class][f"confused_as:{confusion}"] += 1
        rows.append(
            {
                "kind": "false_negative",
                "class_name": gt_class,
                "confused_as": confusion,
                "best_iou": round(best_iou, 4),
                "gt_box": gt["xyxy"],
                "pred_box": best_pred.get("xyxy") if best_pred else None,
                "pred_conf": best_pred.get("conf") if best_pred else None,
            }
        )
    for index, pred in enumerate(preds):
        pred_class = str(pred["class_name"])
        if pred_class not in focus_classes or index in matched_pred_indexes:
            continue
        best_gt_iou = max((bbox_iou(pred["xyxy"], gt["xyxy"]) for gt in gts), default=0.0)
        if best_gt_iou >= iou_threshold:
            continue
        counts[pred_class]["fp"] += 1
        rows.append(
            {
                "kind": "false_positive",
                "class_name": pred_class,
                "best_iou": round(best_gt_iou, 4),
                "gt_box": None,
                "pred_box": pred["xyxy"],
                "pred_conf": pred.get("conf"),
            }
        )
    return {"counts": {name: dict(counts[name]) for name in sorted(counts)}, "failures": rows}


def class_id_mismatches(names: dict[int, str]) -> list[dict[str, object]]:
    mismatches = []
    for index, expected in enumerate(TRAINING_CLASS_ORDER_45):
        actual = names.get(index, "")
        if actual != expected:
            mismatches.append({"class_id": index, "expected": expected, "actual": actual})
    return mismatches


def source_anchor_counts(items: list[dict[str, Any]], focus_classes: tuple[str, ...]) -> dict[str, Any]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for item in items:
        source = str(item.get("source") or "unknown")
        split = str(item.get("split") or "train")
        for class_name in item.get("classes", []):
            if class_name in focus_classes:
                counts[class_name][f"source:{source}"] += 1
                counts[class_name][f"split:{split}"] += 1
                if source in REAL_ANCHOR_SOURCES:
                    counts[class_name]["real_anchor"] += 1
    rows = {}
    for class_name in focus_classes:
        target = PHASE16_ANCHOR_TARGETS.get(class_name, 0)
        real_anchor = counts[class_name]["real_anchor"]
        rows[class_name] = {
            "target_real_anchor": target,
            "real_anchor": real_anchor,
            "missing_real_anchor": max(0, target - real_anchor),
            **dict(counts[class_name]),
        }
    return rows


def _best_prediction(
    gt: dict[str, Any],
    preds: list[dict[str, Any]],
    matched: set[int],
) -> tuple[int, float, dict[str, Any] | None]:
    best_index = -1
    best_iou = 0.0
    best_pred = None
    for index, pred in enumerate(preds):
        if index in matched:
            continue
        iou = bbox_iou(gt["xyxy"], pred["xyxy"])
        if iou > best_iou:
            best_index, best_iou, best_pred = index, iou, pred
    return best_index, best_iou, best_pred


def split_dir(data_root: Path, split: str) -> Path:
    split_name = "valid" if split == "val" else split
    return data_root / "images" / split_name
