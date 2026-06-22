"""Visual quality checks applied immediately before hardware dispatch."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class DispatchVisualSafetyDecision:
    allowed: bool
    reason: str
    area_ratio: float
    sharpness: float


def _clamp_box(
    xyxy: tuple[int, int, int, int],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = xyxy
    x1 = max(0, min(int(x1), width - 1))
    y1 = max(0, min(int(y1), height - 1))
    x2 = max(x1 + 1, min(int(x2), width))
    y2 = max(y1 + 1, min(int(y2), height))
    return x1, y1, x2, y2


def _padded_crop(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> np.ndarray:
    height, width = frame_bgr.shape[:2]
    x1, y1, x2, y2 = _clamp_box(xyxy, width, height)
    pad_x = max(2, int((x2 - x1) * 0.06))
    pad_y = max(2, int((y2 - y1) * 0.06))
    return frame_bgr[
        max(0, y1 - pad_y) : min(height, y2 + pad_y),
        max(0, x1 - pad_x) : min(width, x2 + pad_x),
    ]


def evaluate_dispatch_visual_safety(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
    *,
    max_bbox_area_ratio: float,
    min_sharpness: float,
) -> DispatchVisualSafetyDecision:
    """Reject implausible framing and blurry evidence before a servo command."""
    if frame_bgr.ndim != 3 or frame_bgr.shape[0] < 3 or frame_bgr.shape[1] < 3:
        return DispatchVisualSafetyDecision(False, "camera frame invalid", 1.0, 0.0)

    height, width = frame_bgr.shape[:2]
    x1, y1, x2, y2 = _clamp_box(xyxy, width, height)
    area_ratio = float((x2 - x1) * (y2 - y1)) / float(width * height)
    if 0 < max_bbox_area_ratio < 1.0 and area_ratio > max_bbox_area_ratio:
        return DispatchVisualSafetyDecision(
            False,
            "object framing invalid",
            area_ratio,
            0.0,
        )

    crop = _padded_crop(frame_bgr, xyxy)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if min_sharpness > 0 and sharpness < min_sharpness:
        return DispatchVisualSafetyDecision(False, "camera blurry", area_ratio, sharpness)
    return DispatchVisualSafetyDecision(True, "ready", area_ratio, sharpness)
