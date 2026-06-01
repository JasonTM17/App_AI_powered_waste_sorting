"""Validation and IO helpers for dataset review actions."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.core.waste_categories import (
    TRAINING_CLASS_ORDER_45,
    canonical_class_name,
    default_class_id_for_name,
)


class DatasetReviewError(ValueError):
    """Raised when a requested review action would create invalid metadata."""


def canonical_review_target(cls_name: str | None, cls_id: int | None) -> tuple[str, int]:
    class_name = canonical_class_name(cls_name or "")
    class_id = default_class_id_for_name(class_name)
    if not class_name or class_name not in TRAINING_CLASS_ORDER_45 or class_id is None:
        raise DatasetReviewError(f"Class is outside the 45-class contract: {cls_name}")
    return class_name, int(class_id if class_id is not None else cls_id or 0)


def clean_review_boxes(
    boxes: Sequence[dict[str, Any]],
    *,
    override_name: str | None = None,
    override_id: int | None = None,
) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    for box in boxes:
        xyxy = box.get("xyxy") or []
        if len(xyxy) < 4:
            raise DatasetReviewError("Bbox must have four coordinates")
        try:
            x1, y1, x2, y2 = (float(value) for value in xyxy[:4])
        except (TypeError, ValueError) as exc:
            raise DatasetReviewError("Bbox coordinates must be numeric") from exc
        if x2 <= x1 or y2 <= y1:
            raise DatasetReviewError("Bbox has invalid geometry")
        class_name = override_name or canonical_class_name(str(box.get("cls_name") or ""))
        class_id = override_id if override_id is not None else default_class_id_for_name(class_name)
        if class_name not in TRAINING_CLASS_ORDER_45 or class_id is None:
            raise DatasetReviewError(f"Class is outside the 45-class contract: {class_name}")
        clean.append(
            {
                "cls_id": int(class_id),
                "cls_name": class_name,
                "conf": float(box.get("conf", 1.0) or 1.0),
                "xyxy": [x1, y1, x2, y2],
            }
        )
    return clean


def class_names_from_meta(meta: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for box in meta.get("boxes") or []:
        if not isinstance(box, dict):
            continue
        name = canonical_class_name(str(box.get("cls_name") or "")) or str(box.get("cls_name") or "")
        if name and name not in names:
            names.append(name)
    return names


def read_review_meta(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetReviewError("Dataset metadata is missing or invalid") from exc
    if not isinstance(value, dict):
        raise DatasetReviewError("Dataset metadata must be an object")
    return value


def write_review_meta_atomic(path: Path, meta: dict[str, Any]) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)


def append_review_history(
    meta: dict[str, Any],
    *,
    action: str,
    actor: str,
    reason: str,
    state_before: str,
    state_after: str,
    previous_source: str,
    previous_classes: list[str],
) -> None:
    history = meta.get("review_history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "ts": meta["reviewed_at"],
            "actor": actor,
            "action": action,
            "reason": reason,
            "state_before": state_before,
            "state_after": state_after,
            "previous_source": previous_source,
            "previous_class_names": previous_classes,
        }
    )
    meta["review_history"] = history[-50:]
