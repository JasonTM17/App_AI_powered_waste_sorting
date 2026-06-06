"""Camera frame transforms shared by desktop and web runtimes."""

from __future__ import annotations

from typing import Literal

import cv2
import numpy as np

CameraRotation = Literal[0, 90, 180, 270]


def apply_camera_transform(
    frame: np.ndarray,
    *,
    mirror: bool = False,
    rotation: int = 0,
) -> np.ndarray:
    """Return a frame corrected for camera mounting/orientation."""
    out = frame
    if mirror:
        out = cv2.flip(out, 1)
    rotation = int(rotation)
    if rotation == 90:
        return cv2.rotate(out, cv2.ROTATE_90_CLOCKWISE)
    if rotation == 180:
        return cv2.rotate(out, cv2.ROTATE_180)
    if rotation == 270:
        return cv2.rotate(out, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return out


__all__ = ["CameraRotation", "apply_camera_transform"]
