"""Deterministic, auditable labels for detection history."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.core.three_bin_classifier import parse_three_bin_class_name
from app.core.waste_categories import category_for_class
from app.core.waste_display import normalize_operator_label, waste_display_name

LabelStatus = Literal[
    "model_inferred",
    "metadata_verified",
    "human_verified",
    "needs_review",
    "no_evidence",
]

LABEL_STATUSES: tuple[LabelStatus, ...] = (
    "model_inferred",
    "metadata_verified",
    "human_verified",
    "needs_review",
    "no_evidence",
)

LABEL_STATUS_NAMES: dict[str, str] = {
    "model_inferred": "Suy ra từ model",
    "metadata_verified": "Xác minh từ metadata",
    "human_verified": "Đã được Admin duyệt",
    "needs_review": "Cần duyệt",
    "no_evidence": "Không đủ bằng chứng",
}


@dataclass(frozen=True)
class HistoryLabelDecision:
    display_label: str
    label_status: LabelStatus
    label_source: str
    label_confidence: float | None
    reason: str


def infer_history_label(
    *,
    cls_name: str,
    confidence: float | None,
    meta_path: str | None = None,
    image_available: bool = False,
) -> HistoryLabelDecision:
    """Create a conservative label without mutating the model prediction."""
    clean_class = str(cls_name or "").strip() or "Unknown object"
    operator_label = _operator_label_from_metadata(meta_path)
    if operator_label:
        normalized = normalize_operator_label(operator_label, clean_class)
        if normalized and normalized != waste_display_name(clean_class):
            return HistoryLabelDecision(
                normalized,
                "metadata_verified",
                "capture_metadata",
                1.0,
                "Nhãn người vận hành hợp lệ trong metadata ảnh.",
            )

    command = parse_three_bin_class_name(clean_class)
    if command:
        category = category_for_class(clean_class)
        return HistoryLabelDecision(
            f"Chưa xác định vật – {category.name}",
            "needs_review" if image_available else "no_evidence",
            "three_bin_route_only",
            None,
            "Model chỉ xác định nhóm rác, không xác định vật cụ thể.",
        )

    if clean_class.casefold() == "unknown object":
        return HistoryLabelDecision(
            "Chưa xác định vật",
            "needs_review" if image_available else "no_evidence",
            "unknown_model_class",
            None,
            "Ảnh cần được Admin xem trực tiếp." if image_available else "Không có ảnh để kiểm chứng.",
        )

    return HistoryLabelDecision(
        waste_display_name(clean_class) or clean_class,
        "model_inferred",
        "model_class_catalog",
        _clean_confidence(confidence),
        "Tên hiển thị được ánh xạ từ lớp model gốc.",
    )


def validate_review_label(value: str) -> str:
    clean = normalize_operator_label(value)
    if not clean or clean in {"Chưa xác định vật", "Unknown object"}:
        raise ValueError("Nhãn duyệt phải là tên vật cụ thể.")
    if len(clean) > 120:
        raise ValueError("Nhãn duyệt không được dài quá 120 ký tự.")
    return clean


def _operator_label_from_metadata(meta_path: str | None) -> str:
    if not meta_path:
        return ""
    path = Path(meta_path)
    if not path.is_file():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ""
    for key in ("operator_label", "specialist_label", "suggested_label"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def _clean_confidence(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))


__all__ = [
    "LABEL_STATUSES",
    "LABEL_STATUS_NAMES",
    "HistoryLabelDecision",
    "LabelStatus",
    "infer_history_label",
    "validate_review_label",
]
