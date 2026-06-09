"""Frame quality checks for rejecting black USB camera frames."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

MIN_MEAN_BRIGHTNESS = 2.0
MIN_NON_BLACK_RATIO = 0.01
BLACK_PIXEL_THRESHOLD = 4.0


@dataclass(frozen=True)
class FrameQuality:
    width: int = 0
    height: int = 0
    mean_brightness: float = 0.0
    variance: float = 0.0
    non_black_ratio: float = 0.0
    usable: bool = False
    reason: str = "no frame"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_frame_quality(frame: np.ndarray | None) -> FrameQuality:
    if frame is None:
        return FrameQuality(reason="no frame")
    if not isinstance(frame, np.ndarray) or frame.size == 0:
        return FrameQuality(reason="empty frame")
    height, width = frame.shape[:2]
    if width <= 0 or height <= 0:
        return FrameQuality(reason="invalid frame size")

    if frame.ndim == 2:
        gray = frame.astype(np.float32)
    else:
        gray = frame[..., :3].astype(np.float32).mean(axis=2)

    mean = float(gray.mean())
    variance = float(gray.var())
    non_black_ratio = float(np.count_nonzero(gray > BLACK_PIXEL_THRESHOLD) / gray.size)
    if mean < MIN_MEAN_BRIGHTNESS:
        return FrameQuality(
            width=width,
            height=height,
            mean_brightness=round(mean, 3),
            variance=round(variance, 3),
            non_black_ratio=round(non_black_ratio, 5),
            reason="black frame",
        )
    if non_black_ratio < MIN_NON_BLACK_RATIO:
        return FrameQuality(
            width=width,
            height=height,
            mean_brightness=round(mean, 3),
            variance=round(variance, 3),
            non_black_ratio=round(non_black_ratio, 5),
            reason="too few non-black pixels",
        )
    return FrameQuality(
        width=width,
        height=height,
        mean_brightness=round(mean, 3),
        variance=round(variance, 3),
        non_black_ratio=round(non_black_ratio, 5),
        usable=True,
        reason="ok",
    )


def best_frame_quality(qualities: list[FrameQuality]) -> FrameQuality:
    if not qualities:
        return FrameQuality()
    return max(
        qualities,
        key=lambda item: (
            item.usable,
            item.non_black_ratio,
            item.mean_brightness,
            item.variance,
        ),
    )


def frame_quality_diagnostics(quality: FrameQuality | None, **extra: object) -> dict[str, object]:
    payload = (quality or FrameQuality()).to_dict()
    payload["black_frame"] = not bool(payload.get("usable"))
    payload.update(extra)
    return payload


__all__ = [
    "FrameQuality",
    "best_frame_quality",
    "evaluate_frame_quality",
    "frame_quality_diagnostics",
]
