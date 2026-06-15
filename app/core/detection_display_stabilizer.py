"""Multi-frame hysteresis for operator-facing detection labels."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import replace

from app.core.events import Detection
from app.core.three_bin_classifier import parse_three_bin_class_name


def _bbox_iou(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> float:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    left = max(ax1, bx1)
    top = max(ay1, by1)
    right = min(ax2, bx2)
    bottom = min(ay2, by2)
    intersection = max(0, right - left) * max(0, bottom - top)
    first_area = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    second_area = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def _label_family(detection: Detection) -> str:
    command = parse_three_bin_class_name(detection.cls_name)
    if command is not None:
        return f"route:{command}"
    if detection.cls_name == "Organic":
        return "route:O"
    return f"class:{detection.cls_name}"


class DetectionDisplayStabilizer:
    """Keep one-object labels steady without changing pipeline decisions."""

    def __init__(
        self,
        *,
        window_size: int = 7,
        acquire_frames: int = 3,
        switch_frames: int = 5,
        switch_consecutive_frames: int = 3,
        max_missed_frames: int = 3,
        object_iou_threshold: float = 0.12,
    ) -> None:
        self.window_size = max(3, int(window_size))
        self.acquire_frames = max(1, int(acquire_frames))
        self.switch_frames = max(self.acquire_frames, int(switch_frames))
        self.switch_consecutive_frames = max(1, int(switch_consecutive_frames))
        self.max_missed_frames = max(0, int(max_missed_frames))
        self.object_iou_threshold = max(0.0, min(1.0, float(object_iou_threshold)))
        self._samples: deque[Detection | None] = deque(maxlen=self.window_size)
        self._stable_family = ""
        self._stable_detection: Detection | None = None
        self._missed_frames = 0

    def reset(self) -> None:
        self._samples.clear()
        self._stable_family = ""
        self._stable_detection = None
        self._missed_frames = 0

    def update(self, detections: list[Detection]) -> list[Detection]:
        if len(detections) > 1:
            self.reset()
            return list(detections)
        if not detections:
            return self._handle_empty_frame()

        current = detections[0]
        if (
            self._stable_detection is not None
            and _bbox_iou(self._stable_detection.xyxy, current.xyxy)
            < self.object_iou_threshold
        ):
            self.reset()

        self._missed_frames = 0
        self._samples.append(current)
        current_family = _label_family(current)
        family_counts = Counter(
            _label_family(sample) for sample in self._samples if sample is not None
        )

        if not self._stable_family:
            if family_counts[current_family] < self.acquire_frames:
                return []
            self._stable_family = current_family
        elif current_family != self._stable_family:
            recent_families = [
                _label_family(sample) for sample in self._samples if sample is not None
            ]
            consecutive = recent_families[-self.switch_consecutive_frames :]
            should_switch = (
                family_counts[current_family] >= self.switch_frames
                and len(consecutive) == self.switch_consecutive_frames
                and all(family == current_family for family in consecutive)
            )
            if should_switch:
                self._stable_family = current_family

        stable_samples = [
            sample
            for sample in self._samples
            if sample is not None and _label_family(sample) == self._stable_family
        ]
        if not stable_samples:
            return [self._stable_detection] if self._stable_detection is not None else []

        representative = max(
            stable_samples,
            key=lambda sample: (
                parse_three_bin_class_name(sample.cls_name) is None,
                sample.conf,
            ),
        )
        latest = stable_samples[-1]
        average_confidence = sum(sample.conf for sample in stable_samples) / len(stable_samples)
        self._stable_detection = replace(
            representative,
            conf=average_confidence,
            xyxy=latest.xyxy,
        )
        return [self._stable_detection]

    def _handle_empty_frame(self) -> list[Detection]:
        self._missed_frames += 1
        self._samples.append(None)
        if self._missed_frames > self.max_missed_frames:
            self.reset()
            return []
        return [self._stable_detection] if self._stable_detection is not None else []


__all__ = ["DetectionDisplayStabilizer"]
