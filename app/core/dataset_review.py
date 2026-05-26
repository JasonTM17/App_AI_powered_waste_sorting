"""Atomic dataset review actions with audit metadata."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.dataset_catalog import DatasetCatalog
from app.core.dataset_review_utils import (
    DatasetReviewError,
    append_review_history,
    canonical_review_target,
    class_names_from_meta,
    clean_review_boxes,
    read_review_meta,
    write_review_meta_atomic,
)
from app.core.dataset_trust import classify_dataset_item

REVIEW_ACTIONS = {
    "approve",
    "relabel",
    "bbox_approved",
    "needs_annotation",
    "hard_negative",
    "holdout",
    "quarantine",
    "exclude",
}


@dataclass(frozen=True)
class DatasetReviewRequest:
    action: str
    cls_name: str | None = None
    cls_id: int | None = None
    reason: str = ""
    actor: str = "admin"
    boxes: Sequence[dict[str, Any]] = field(default_factory=tuple)


def review_dataset_item(
    item_id: str,
    request: DatasetReviewRequest,
    *,
    catalog_path: Path,
) -> dict[str, Any]:
    catalog = DatasetCatalog(catalog_path)
    try:
        item = catalog.get_item(item_id)
    finally:
        catalog.close()
    if item is None:
        raise DatasetReviewError("Dataset item not found")
    return apply_dataset_review_action(Path(str(item["image_path"])), request, catalog_path=catalog_path)


def apply_dataset_review_action(
    image_path: Path,
    request: DatasetReviewRequest,
    *,
    catalog_path: Path | None = None,
) -> dict[str, Any]:
    action = request.action.strip().lower()
    if action not in REVIEW_ACTIONS:
        raise DatasetReviewError(f"Unsupported review action: {request.action}")
    if not image_path.exists():
        raise DatasetReviewError("Dataset image not found")
    meta_path = image_path.with_suffix(".json")
    meta = read_review_meta(meta_path)
    before = classify_dataset_item(meta)
    previous_source = str(meta.get("source") or "unknown")
    previous_classes = class_names_from_meta(meta)

    if action in {"approve", "bbox_approved"}:
        _apply_approve(meta, request)
    elif action == "relabel":
        _apply_relabel(meta, request)
    elif action == "needs_annotation":
        _apply_needs_annotation(meta, request)
    elif action == "hard_negative":
        _apply_hard_negative(meta)
    elif action == "holdout":
        _apply_holdout(meta)
    elif action == "quarantine":
        _apply_quarantine(meta, request)
    elif action == "exclude":
        _apply_exclude(meta, request)

    now = datetime.now().isoformat()
    actor = request.actor.strip() or "admin"
    reason = request.reason.strip()
    after = classify_dataset_item(meta)
    meta.update(
        {
            "reviewed_at": now,
            "reviewed_by": actor,
            "review_decision": action,
            "review_reason": reason,
            "trust_state_before": before.state.value,
            "trust_reasons_before": list(before.reasons),
            "trust_state_after": after.state.value,
            "trust_reasons_after": list(after.reasons),
        }
    )
    append_review_history(
        meta,
        action=action,
        actor=actor,
        reason=reason,
        state_before=before.state.value,
        state_after=after.state.value,
        previous_source=previous_source,
        previous_classes=previous_classes,
    )
    write_review_meta_atomic(meta_path, meta)
    if catalog_path is not None:
        catalog = DatasetCatalog(catalog_path)
        try:
            catalog.upsert_item(image_path, meta)
        finally:
            catalog.close()
    return meta


def _apply_approve(meta: dict[str, Any], request: DatasetReviewRequest) -> None:
    if request.boxes:
        meta["boxes"] = clean_review_boxes(request.boxes)
    if not meta.get("boxes"):
        raise DatasetReviewError("Approve requires at least one bbox")
    meta["reviewed"] = True
    meta["needs_annotation"] = False
    meta["bbox_reviewed"] = True
    meta["training_excluded"] = False
    meta["recognition_enabled"] = True
    meta.pop("training_exclusion_reason", None)
    meta.pop("quarantined", None)
    meta.pop("quarantine_reason", None)


def _apply_relabel(meta: dict[str, Any], request: DatasetReviewRequest) -> None:
    class_name, class_id = canonical_review_target(request.cls_name, request.cls_id)
    source_boxes = request.boxes or meta.get("boxes") or []
    boxes = clean_review_boxes(source_boxes, override_name=class_name, override_id=class_id)
    if not boxes:
        raise DatasetReviewError("Relabel requires at least one bbox")
    meta["previous_class_names"] = class_names_from_meta(meta)
    meta["boxes"] = boxes
    _apply_approve(meta, DatasetReviewRequest(action="approve", actor=request.actor, reason=request.reason))


def _apply_needs_annotation(meta: dict[str, Any], request: DatasetReviewRequest) -> None:
    meta["reviewed"] = False
    meta["needs_annotation"] = True
    meta["bbox_reviewed"] = False
    meta["training_excluded"] = True
    meta["training_exclusion_reason"] = request.reason.strip() or "needs_annotation"


def _apply_hard_negative(meta: dict[str, Any]) -> None:
    source = str(meta.get("source") or "unknown")
    if source != "hard_negative":
        meta["previous_source"] = source
    meta["source"] = "hard_negative"
    meta["hard_negative"] = True
    meta["boxes"] = []
    meta["reviewed"] = True
    meta["needs_annotation"] = False
    meta["training_excluded"] = True
    meta["recognition_enabled"] = False


def _apply_holdout(meta: dict[str, Any]) -> None:
    if not meta.get("boxes"):
        raise DatasetReviewError("Holdout requires at least one bbox")
    meta["reviewed"] = True
    meta["bbox_reviewed"] = True
    meta["needs_annotation"] = False
    meta["holdout"] = True
    meta["split"] = "test"
    meta["split_lock"] = True
    meta["recognition_enabled"] = False


def _apply_quarantine(meta: dict[str, Any], request: DatasetReviewRequest) -> None:
    meta["quarantined"] = True
    meta["training_excluded"] = True
    meta["quarantine_reason"] = request.reason.strip() or "review_quarantine"
    meta["recognition_enabled"] = False


def _apply_exclude(meta: dict[str, Any], request: DatasetReviewRequest) -> None:
    meta["training_excluded"] = True
    meta["training_exclusion_reason"] = request.reason.strip() or "review_excluded"
    meta["recognition_enabled"] = False
