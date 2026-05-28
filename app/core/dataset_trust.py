"""Canonical trust and taxonomy decisions for dataset queue metadata."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.core.downloaded_zip_intake import DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE
from app.core.licensed_source_ingestion import source_manifest_issues
from app.core.training_source_flags import is_train_only_supplemental_meta
from app.core.waste_categories import TRAINING_CLASS_ORDER_45, canonical_class_name


class DatasetTrustState(str, Enum):
    TRAINABLE = "trainable"
    NEEDS_REVIEW = "needs_review"
    QUARANTINE = "quarantine"
    HARD_NEGATIVE = "hard_negative"
    HOLDOUT = "holdout"
    EXCLUDED = "excluded"


class DatasetBlockReason(str, Enum):
    INVALID_META = "invalid_meta"
    UNTRUSTED_SOURCE = "untrusted_source"
    UNKNOWN_LABELS = "unknown_labels"
    TRAINING_EXCLUDED = "training_excluded"
    QUARANTINED = "quarantined"
    REVIEW_REQUIRED = "review_required"
    HARD_NEGATIVE = "hard_negative"
    HOLDOUT_ONLY = "holdout_only"
    NO_BOXES = "no_boxes"
    OFF_TAXONOMY = "off_taxonomy"
    INVALID_BBOX = "invalid_bbox"
    SOURCE_LICENSE_ISSUE = "source_license_issue"
    SUPPLEMENTAL_TRAIN_ONLY = "supplemental_train_only"


@dataclass(frozen=True)
class TrustDecision:
    state: DatasetTrustState
    reasons: tuple[str, ...]
    source: str
    class_names: tuple[str, ...] = ()
    source_issues: tuple[str, ...] = ()

    @property
    def trainable(self) -> bool:
        return self.state is DatasetTrustState.TRAINABLE


TRUSTED_SOURCES = {
    "auto_low_conf",
    "manual_import",
    "manual_phone_import",
    "manual_camera_capture",
    "manual_web_import",
    "roboflow",
    "hard_negative",
    "negative",
    "empty_tray",
    "camera_blur_augmented",
    "kaggle_auto_bbox_classification",
    "kaggle_garbage_detection_vn",
    "kaggle_mini_trash_vietnam",
    "waste_detection_2_candidate",
    DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE,
}
REVIEW_REQUIRED_SOURCES = {
    "auto_low_conf",
    "manual_phone_import",
    "manual_camera_capture",
    "manual_web_import",
    DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE,
}
HARD_NEGATIVE_SOURCES = {"hard_negative", "negative", "empty_tray"}
TRUSTED_SOURCE_PREFIXES = ("roboflow_", "kaggle_", "camera_blur_augmented", "generated", "imagegen", "synthetic")
TRAINING_CLASS_SET = frozenset(TRAINING_CLASS_ORDER_45)


def classify_dataset_item(meta: dict[str, Any] | None) -> TrustDecision:
    if not isinstance(meta, dict):
        return _decision(DatasetTrustState.QUARANTINE, "unknown", [DatasetBlockReason.INVALID_META])

    source = str(meta.get("source") or "unknown")
    class_names, class_reasons = canonical_classes_from_meta(meta)
    reasons: list[str | DatasetBlockReason] = []

    if is_hard_negative_meta(meta):
        return _decision(DatasetTrustState.HARD_NEGATIVE, source, [DatasetBlockReason.HARD_NEGATIVE], class_names)
    if meta.get("quarantined") is True:
        return _decision(DatasetTrustState.QUARANTINE, source, [DatasetBlockReason.QUARANTINED], class_names)
    if (
        meta.get("training_excluded") is True
        and str(meta.get("training_exclusion_reason") or "") in {"bbox_saved_pending_review", "needs_annotation"}
    ):
        return _decision(
            DatasetTrustState.NEEDS_REVIEW,
            source,
            [DatasetBlockReason.TRAINING_EXCLUDED, DatasetBlockReason.REVIEW_REQUIRED],
            class_names,
        )
    if meta.get("training_excluded") is True:
        return _decision(DatasetTrustState.EXCLUDED, source, [DatasetBlockReason.TRAINING_EXCLUDED], class_names)

    if not is_trusted_source_name(source):
        reasons.append(DatasetBlockReason.UNTRUSTED_SOURCE)
    if meta.get("unknown_labels"):
        reasons.append(DatasetBlockReason.UNKNOWN_LABELS)
    reasons.extend(class_reasons)

    manifest_issues = tuple(source_manifest_issues(meta))
    if manifest_issues:
        reasons.append(DatasetBlockReason.SOURCE_LICENSE_ISSUE)
        reasons.extend(manifest_issues)

    if _has_quarantine_reason(reasons):
        return _decision(DatasetTrustState.QUARANTINE, source, reasons, class_names, manifest_issues)

    if _needs_review(meta, source):
        return _decision(DatasetTrustState.NEEDS_REVIEW, source, [*reasons, DatasetBlockReason.REVIEW_REQUIRED], class_names)

    if is_holdout_meta(meta):
        return _decision(DatasetTrustState.HOLDOUT, source, [*reasons, DatasetBlockReason.HOLDOUT_ONLY], class_names)

    if is_train_only_supplemental_meta(meta) and str(meta.get("split") or "train").lower() != "train":
        return _decision(DatasetTrustState.EXCLUDED, source, [*reasons, DatasetBlockReason.SUPPLEMENTAL_TRAIN_ONLY], class_names)

    return _decision(DatasetTrustState.TRAINABLE, source, reasons, class_names, manifest_issues)


def is_trusted_source_name(source: str) -> bool:
    clean = str(source or "unknown")
    if clean in {"unknown", "untrusted"}:
        return False
    if clean in TRUSTED_SOURCES:
        return True
    return clean.startswith(TRUSTED_SOURCE_PREFIXES) or clean.endswith("_candidate")


def is_trusted_meta(meta: dict[str, Any]) -> bool:
    decision = classify_dataset_item(meta)
    return decision.state is not DatasetTrustState.QUARANTINE


def is_trainable_meta(meta: dict[str, Any]) -> bool:
    return classify_dataset_item(meta).trainable


def is_holdout_meta(meta: dict[str, Any]) -> bool:
    return meta.get("holdout") is True or str(meta.get("split") or "").lower() == "test"


def is_hard_negative_meta(meta: dict[str, Any]) -> bool:
    source = str(meta.get("source") or "unknown")
    return source in HARD_NEGATIVE_SOURCES or meta.get("hard_negative") is True


def canonical_classes_from_meta(meta: dict[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    boxes = meta.get("boxes") or []
    if not boxes:
        return (), (DatasetBlockReason.NO_BOXES.value,)
    class_names: list[str] = []
    reasons: set[str] = set()
    for box in boxes:
        if not isinstance(box, dict):
            reasons.add(DatasetBlockReason.INVALID_BBOX.value)
            continue
        class_name = canonical_class_name(str(box.get("cls_name") or ""))
        if class_name not in TRAINING_CLASS_SET:
            reasons.add(DatasetBlockReason.OFF_TAXONOMY.value)
        elif class_name not in class_names:
            class_names.append(class_name)
        if not _valid_bbox(box.get("xyxy")):
            reasons.add(DatasetBlockReason.INVALID_BBOX.value)
    return tuple(class_names), tuple(sorted(reasons))


def _needs_review(meta: dict[str, Any], source: str) -> bool:
    if source not in REVIEW_REQUIRED_SOURCES:
        return False
    return meta.get("reviewed") is not True or meta.get("bbox_reviewed") is not True


def _valid_bbox(xyxy: object) -> bool:
    if not isinstance(xyxy, list | tuple) or len(xyxy) < 4:
        return False
    try:
        x1, y1, x2, y2 = (float(value) for value in xyxy[:4])
    except (TypeError, ValueError):
        return False
    return x2 > x1 and y2 > y1


def _has_quarantine_reason(reasons: list[str | DatasetBlockReason]) -> bool:
    quarantine = {
        DatasetBlockReason.INVALID_META.value,
        DatasetBlockReason.UNTRUSTED_SOURCE.value,
        DatasetBlockReason.UNKNOWN_LABELS.value,
        DatasetBlockReason.NO_BOXES.value,
        DatasetBlockReason.OFF_TAXONOMY.value,
        DatasetBlockReason.INVALID_BBOX.value,
        DatasetBlockReason.SOURCE_LICENSE_ISSUE.value,
    }
    return bool({str(reason.value if isinstance(reason, DatasetBlockReason) else reason) for reason in reasons} & quarantine)


def _decision(
    state: DatasetTrustState,
    source: str,
    reasons: list[str | DatasetBlockReason],
    class_names: tuple[str, ...] = (),
    source_issues: tuple[str, ...] = (),
) -> TrustDecision:
    clean_reasons = tuple(sorted({str(reason.value if isinstance(reason, DatasetBlockReason) else reason) for reason in reasons}))
    return TrustDecision(state=state, reasons=clean_reasons, source=source, class_names=class_names, source_issues=source_issues)
