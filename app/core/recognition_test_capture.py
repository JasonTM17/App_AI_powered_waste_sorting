"""Capture and model evidence helpers for guided recognition tests."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.core.events import Detection
from app.core.recognition_test import RecognitionTrialResult
from app.utils.paths import recognition_test_captures_dir


def model_sha256(model_path: str | Path) -> str:
    path = Path(model_path)
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as model_file:
        for chunk in iter(lambda: model_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_recognition_test_capture(
    result: RecognitionTrialResult,
    frame_bgr: np.ndarray,
    detections: Sequence[Detection],
) -> tuple[str, str, str]:
    sample_dir = (
        recognition_test_captures_dir()
        / result.session_id
        / _safe_name(result.sample_label)
    )
    sample_dir.mkdir(parents=True, exist_ok=True)
    stem = f"trial-{result.trial_number:02d}-{result.id[:8]}"
    raw_path = sample_dir / f"{stem}-raw.jpg"
    annotated_path = sample_dir / f"{stem}-annotated.jpg"
    metadata_path = sample_dir / f"{stem}.json"

    image = Image.fromarray(frame_bgr[:, :, ::-1])
    image.save(raw_path, format="JPEG", quality=95)

    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    font = ImageFont.load_default()
    for detection in detections:
        x1, y1, x2, y2 = detection.xyxy
        draw.rectangle((x1, y1, x2, y2), outline=(0, 220, 120), width=4)
        draw.text(
            (x1 + 4, max(0, y1 - 16)),
            f"{detection.cls_name} {detection.conf:.2f}",
            fill=(255, 255, 255),
            stroke_width=2,
            stroke_fill=(0, 0, 0),
            font=font,
        )
    summary = (
        f"Expected: {result.expected_class} | "
        f"Predicted: {result.predicted_class or '-'} | {result.verdict}"
    )
    draw.rectangle((0, 0, annotated.width, 26), fill=(0, 0, 0))
    draw.text((8, 7), summary, fill=(255, 255, 255), font=font)
    annotated.save(annotated_path, format="JPEG", quality=95)

    metadata = result.to_dict()
    metadata["raw_image_path"] = str(raw_path)
    metadata["annotated_image_path"] = str(annotated_path)
    metadata["detections"] = [
        {
            "class_id": item.cls_id,
            "class_name": item.cls_name,
            "confidence": item.conf,
            "xyxy": list(item.xyxy),
        }
        for item in detections
    ]
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(raw_path), str(annotated_path), str(metadata_path)


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return cleaned.strip("-") or "sample"
