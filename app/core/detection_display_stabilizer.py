"""Multi-frame hysteresis for operator-facing detection labels."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import replace

from app.core.events import Detection
from app.core.three_bin_classifier import parse_three_bin_class_name
from app.core.waste_categories import category_for_known_class


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


def _label_family(detection: Detection, *, group_by_route: bool = False) -> str:
    command = parse_three_bin_class_name(detection.cls_name)
    if command is not None:
        return f"route:{command}"
    if group_by_route:
        category = category_for_known_class(detection.cls_name)
        if category is not None:
            return f"route:{category.code}"
    elif detection.cls_name == "Organic":
        return "route:O"
    return f"class:{detection.cls_name}"


def _exact_label_key(detection: Detection) -> tuple[str, str] | None:
    if parse_three_bin_class_name(detection.cls_name) is not None:
        return None
    return detection.cls_name, detection.operator_label


def _has_operator_label(key: tuple[str, str] | None) -> bool:
    return bool(key is not None and str(key[1] or "").strip())


def _generic_route_detection(
    family: str,
    samples: list[Detection],
) -> Detection:
    command = family.removeprefix("route:")
    latest = samples[-1]
    confidence = sum(sample.conf for sample in samples) / len(samples)
    cls_ids = {"O": -301, "R": -302, "I": -303}
    return Detection(
        cls_id=cls_ids.get(command, -300),
        cls_name=f"Kaggle 3-bin {command}",
        conf=confidence,
        xyxy=latest.xyxy,
        source="temporal_route_consensus",
    )


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
        group_by_route: bool = False,
        exact_acquire_frames: int = 3,
        exact_switch_frames: int = 5,
        exact_switch_consecutive_frames: int = 3,
    ) -> None:
        self.window_size = max(3, int(window_size))
        self.acquire_frames = max(1, int(acquire_frames))
        self.switch_frames = max(self.acquire_frames, int(switch_frames))
        self.switch_consecutive_frames = max(1, int(switch_consecutive_frames))
        self.max_missed_frames = max(0, int(max_missed_frames))
        self.object_iou_threshold = max(0.0, min(1.0, float(object_iou_threshold)))
        self.group_by_route = bool(group_by_route)
        self.exact_acquire_frames = max(1, int(exact_acquire_frames))
        self.exact_switch_frames = max(
            self.exact_acquire_frames,
            int(exact_switch_frames),
        )
        self.exact_switch_consecutive_frames = max(
            1,
            int(exact_switch_consecutive_frames),
        )
        self._samples: deque[Detection | None] = deque(maxlen=self.window_size)
        self._stable_family = ""
        self._stable_detection: Detection | None = None
        self._stable_exact_key: tuple[str, str] | None = None
        self._missed_frames = 0

    def reset(self) -> None:
        self._samples.clear()
        self._stable_family = ""
        self._stable_detection = None
        self._stable_exact_key = None
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
        current_family = _label_family(current, group_by_route=self.group_by_route)
        family_counts = Counter(
            _label_family(sample, group_by_route=self.group_by_route)
            for sample in self._samples
            if sample is not None
        )

        if not self._stable_family:
            if family_counts[current_family] < self.acquire_frames:
                return []
            self._stable_family = current_family
        elif current_family != self._stable_family:
            recent_families = [
                _label_family(sample, group_by_route=self.group_by_route)
                for sample in self._samples
                if sample is not None
            ]
            consecutive = recent_families[-self.switch_consecutive_frames :]
            should_switch = (
                family_counts[current_family] >= self.switch_frames
                and len(consecutive) == self.switch_consecutive_frames
                and all(family == current_family for family in consecutive)
            )
            if should_switch:
                self._stable_family = current_family
                self._stable_exact_key = None

        stable_samples = [
            sample
            for sample in self._samples
            if sample is not None
            and _label_family(sample, group_by_route=self.group_by_route)
            == self._stable_family
        ]
        if not stable_samples:
            return [self._stable_detection] if self._stable_detection is not None else []

        if self.group_by_route and self._stable_family.startswith("route:"):
            return [self._stable_route_detection(stable_samples)]

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

    def _stable_route_detection(self, samples: list[Detection]) -> Detection:
        exact_samples = [sample for sample in samples if _exact_label_key(sample) is not None]
        exact_counts = Counter(_exact_label_key(sample) for sample in exact_samples)
        if exact_counts:
            candidate, candidate_count = exact_counts.most_common(1)[0]
            trusted_exact_keys = {key for key in exact_counts if _has_operator_label(key)}
            exact_keys = [_exact_label_key(sample) for sample in exact_samples]
            required = (
                self.exact_acquire_frames
                if self._stable_exact_key is None
                else self.exact_switch_frames
            )
            consecutive = exact_keys[-self.exact_switch_consecutive_frames :]
            can_acquire_trusted_label = (
                self._stable_exact_key is None
                and len(trusted_exact_keys) == 1
                and candidate in trusted_exact_keys
            )
            can_select = can_acquire_trusted_label or (
                candidate_count >= required
                and (
                    self._stable_exact_key is None
                    or candidate == self._stable_exact_key
                    or (
                        len(consecutive) == self.exact_switch_consecutive_frames
                        and all(key == candidate for key in consecutive)
                    )
                )
            )
            if can_select:
                self._stable_exact_key = candidate

        if self._stable_exact_key is None:
            self._stable_detection = _generic_route_detection(self._stable_family, samples)
            return self._stable_detection

        matching = [
            sample
            for sample in exact_samples
            if _exact_label_key(sample) == self._stable_exact_key
        ]
        if not matching:
            self._stable_exact_key = None
            self._stable_detection = _generic_route_detection(self._stable_family, samples)
            return self._stable_detection
        latest = samples[-1]
        confidence = sum(sample.conf for sample in matching) / len(matching)
        self._stable_detection = replace(matching[-1], conf=confidence, xyxy=latest.xyxy)
        return self._stable_detection

    def _handle_empty_frame(self) -> list[Detection]:
        self._missed_frames += 1
        self._samples.append(None)
        if self._missed_frames > self.max_missed_frames:
            self.reset()
            return []
        return [self._stable_detection] if self._stable_detection is not None else []


__all__ = ["DetectionDisplayStabilizer"]
