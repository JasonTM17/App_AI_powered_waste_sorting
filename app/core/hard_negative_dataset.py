"""Hard-negative dataset capture and safety-eval helpers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.dataset_catalog import DatasetCatalog

HARD_NEGATIVE_SOURCE = "hard_negative"
HARD_NEGATIVE_REASONS = (
    "empty_tray",
    "hand_only",
    "background_clutter",
    "two_objects",
    "outside_roi",
    "cloth_non_waste",
    "wire_or_fixture",
    "blur_or_motion",
)
HARD_NEGATIVE_REASON_LABELS = {
    "empty_tray": "Khay trống",
    "hand_only": "Chỉ có tay",
    "background_clutter": "Nền lộn xộn",
    "two_objects": "Hai vật trên bàn",
    "outside_roi": "Ngoài ROI",
    "cloth_non_waste": "Vải không phải rác",
    "wire_or_fixture": "Dây/khung cố định",
    "blur_or_motion": "Mờ/chuyển động",
}
HARD_NEGATIVE_EXPECTED_OUTCOMES = {
    "empty_tray": "no_detection",
    "hand_only": "no_dispatch",
    "background_clutter": "no_dispatch",
    "two_objects": "multi_object_warning",
    "outside_roi": "outside_roi_block",
    "cloth_non_waste": "no_dispatch",
    "wire_or_fixture": "no_dispatch",
    "blur_or_motion": "no_dispatch",
}


def normalize_hard_negative_reason(reason: str) -> str:
    clean = str(reason or "").strip().lower().replace("-", "_").replace(" ", "_")
    if clean not in HARD_NEGATIVE_REASONS:
        allowed = ", ".join(HARD_NEGATIVE_REASONS)
        raise ValueError(f"hard_negative_reason must be one of: {allowed}")
    return clean


def capture_hard_negative_frame(
    frame_bgr: object,
    queue_dir: Path,
    reason: str,
    *,
    catalog_path: Path | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> Path:
    """Save a camera frame as evaluation-only hard negative, never as train label."""
    import numpy as np
    from PIL import Image

    clean_reason = normalize_hard_negative_reason(reason)
    arr = np.asarray(frame_bgr)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError("camera frame must be a BGR image")
    rgb = np.ascontiguousarray(arr[:, :, :3][:, :, ::-1])
    image = Image.fromarray(rgb)
    width, height = image.size

    queue_dir.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex[:12]
    img_path = queue_dir / f"hard_negative_{clean_reason}_{uid}.jpg"
    image.save(img_path, format="JPEG", quality=92)

    meta: dict[str, Any] = {
        "ts": datetime.now().isoformat(),
        "source": HARD_NEGATIVE_SOURCE,
        "hard_negative": True,
        "hard_negative_reason": clean_reason,
        "hard_negative_label": HARD_NEGATIVE_REASON_LABELS[clean_reason],
        "expected_outcome": HARD_NEGATIVE_EXPECTED_OUTCOMES[clean_reason],
        "reviewed": True,
        "bbox_reviewed": True,
        "needs_annotation": False,
        "training_excluded": True,
        "training_exclusion_reason": HARD_NEGATIVE_SOURCE,
        "evaluation_enabled": True,
        "recognition_enabled": False,
        "width": int(width),
        "height": int(height),
        "boxes": [],
    }
    if extra_meta:
        meta.update(extra_meta)
    meta.update(
        {
            "source": HARD_NEGATIVE_SOURCE,
            "hard_negative": True,
            "hard_negative_reason": clean_reason,
            "expected_outcome": HARD_NEGATIVE_EXPECTED_OUTCOMES[clean_reason],
            "training_excluded": True,
            "training_exclusion_reason": HARD_NEGATIVE_SOURCE,
            "evaluation_enabled": True,
            "recognition_enabled": False,
            "boxes": [],
        }
    )
    img_path.with_suffix(".json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if catalog_path is not None:
        catalog = DatasetCatalog(catalog_path)
        try:
            catalog.upsert_item(img_path, meta)
        finally:
            catalog.close()
    return img_path


__all__ = [
    "HARD_NEGATIVE_EXPECTED_OUTCOMES",
    "HARD_NEGATIVE_REASONS",
    "HARD_NEGATIVE_REASON_LABELS",
    "HARD_NEGATIVE_SOURCE",
    "capture_hard_negative_frame",
    "normalize_hard_negative_reason",
]
