"""Fallback object presence detector for classes the YOLO model has not learned yet."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from app.core.events import Detection

RoiFilter = Callable[[tuple[int, int, int, int]], bool]
MAX_UNKNOWN_BBOX_COVERAGE = 0.45


@dataclass(frozen=True)
class UnknownObjectCandidate:
    xyxy: tuple[int, int, int, int]
    confidence: float
    source: str


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    x1 = max(ax1, bx1)
    y1 = max(ay1, by1)
    x2 = min(ax2, bx2)
    y2 = min(ay2, by2)
    iw = max(0, x2 - x1)
    ih = max(0, y2 - y1)
    inter = iw * ih
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union else 0.0


class UnknownObjectFallback:
    """Detect a stable unknown object without pretending to know its real class."""

    def __init__(self) -> None:
        self._background: np.ndarray | None = None
        self._background_frames = 0
        self._last_xyxy: tuple[int, int, int, int] | None = None
        self._stable_count = 0

    def reset(self) -> None:
        self._background = None
        self._background_frames = 0
        self._last_xyxy = None
        self._stable_count = 0

    def detect(
        self,
        frame_bgr: np.ndarray,
        raw_detections: list[Detection],
        *,
        class_name: str,
        roi_filter: RoiFilter,
        min_raw_confidence: float,
        min_area_ratio: float,
        stable_frames: int,
        warmup_frames: int,
    ) -> Detection | None:
        candidate = self._from_low_conf_yolo(
            raw_detections,
            roi_filter=roi_filter,
            min_raw_confidence=min_raw_confidence,
        )
        if candidate is None:
            candidate = self._from_background_delta(
                frame_bgr,
                roi_filter=roi_filter,
                min_area_ratio=min_area_ratio,
                warmup_frames=warmup_frames,
            )
        if candidate is None:
            candidate = self._from_static_contrast(
                frame_bgr,
                roi_filter=roi_filter,
                min_area_ratio=min_area_ratio,
            )
        if candidate is None:
            self._last_xyxy = None
            self._stable_count = 0
            return None
        if self._last_xyxy is not None and _iou(self._last_xyxy, candidate.xyxy) >= 0.25:
            self._stable_count += 1
        else:
            self._stable_count = 1
        self._last_xyxy = candidate.xyxy
        if self._stable_count < stable_frames:
            return None
        return Detection(-1, class_name, candidate.confidence, candidate.xyxy)

    @staticmethod
    def _from_low_conf_yolo(
        raw_detections: list[Detection],
        *,
        roi_filter: RoiFilter,
        min_raw_confidence: float,
    ) -> UnknownObjectCandidate | None:
        candidates = [
            d
            for d in raw_detections
            if d.conf >= min_raw_confidence and roi_filter(d.xyxy)
        ]
        if not candidates:
            return None
        best = max(
            candidates,
            key=lambda d: d.conf * max(1, d.xyxy[2] - d.xyxy[0]) * max(1, d.xyxy[3] - d.xyxy[1]),
        )
        return UnknownObjectCandidate(best.xyxy, max(0.05, min(0.39, best.conf)), "low_conf_yolo")

    def _from_background_delta(
        self,
        frame_bgr: np.ndarray,
        *,
        roi_filter: RoiFilter,
        min_area_ratio: float,
        warmup_frames: int,
    ) -> UnknownObjectCandidate | None:
        try:
            import cv2
        except Exception:
            return None
        if frame_bgr.size == 0:
            return None
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (7, 7), 0)
        if self._background is None:
            self._background = gray.astype("float32")
            self._background_frames = 1
            return None
        if self._background_frames < warmup_frames:
            cv2.accumulateWeighted(gray, self._background, 0.35)
            self._background_frames += 1
            return None
        background_u8 = cv2.convertScaleAbs(self._background)
        diff = cv2.absdiff(background_u8, gray)
        _, mask = cv2.threshold(diff, 28, 255, cv2.THRESH_BINARY)
        kernel = np.ones((5, 5), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        height, width = gray.shape[:2]
        min_area = float(width * height) * min_area_ratio
        boxes: list[tuple[int, int, int, int]] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            xyxy = (int(x), int(y), int(x + w), int(y + h))
            if roi_filter(xyxy):
                boxes.append(xyxy)
        if not boxes:
            cv2.accumulateWeighted(gray, self._background, 0.03)
            return None
        x1 = min(box[0] for box in boxes)
        y1 = min(box[1] for box in boxes)
        x2 = max(box[2] for box in boxes)
        y2 = max(box[3] for box in boxes)
        area_ratio = ((x2 - x1) * (y2 - y1)) / float(width * height)
        if area_ratio > MAX_UNKNOWN_BBOX_COVERAGE:
            cv2.accumulateWeighted(gray, self._background, 0.03)
            return None
        confidence = max(0.10, min(0.39, area_ratio / max(min_area_ratio * 8.0, 1e-6)))
        return UnknownObjectCandidate((x1, y1, x2, y2), confidence, "background_delta")

    @staticmethod
    def _from_static_contrast(
        frame_bgr: np.ndarray,
        *,
        roi_filter: RoiFilter,
        min_area_ratio: float,
    ) -> UnknownObjectCandidate | None:
        """Find a static unknown object on a plain tray/table.

        The background model is still preferred, but a pen already present when
        the camera starts can be learned into that background. This fallback
        looks for compact colored/dark regions, which catches common tray items
        without treating the whole bright tabletop as an object.
        """
        try:
            import cv2
        except Exception:
            return None
        if frame_bgr.size == 0:
            return None

        height, width = frame_bgr.shape[:2]
        frame_area = float(width * height)
        min_bbox_area = frame_area * min_area_ratio

        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        _h, saturation, value = cv2.split(hsv)
        colored = (saturation > 42) & (value > 35) & (value < 250)
        dark = (value < 105) & (saturation > 12)
        mask = np.where(colored | dark, 255, 0).astype("uint8")

        kernel = np.ones((5, 5), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: list[tuple[int, int, int, int, float]] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w <= 2 or h <= 2:
                continue
            xyxy = (int(x), int(y), int(x + w), int(y + h))
            if not roi_filter(xyxy):
                continue
            bbox_area = float(w * h)
            if bbox_area < min_bbox_area:
                continue
            contour_area = float(cv2.contourArea(contour))
            fill_ratio = contour_area / max(bbox_area, 1.0)
            coverage = bbox_area / max(frame_area, 1.0)
            longest = max(w, h)
            shortest = max(1, min(w, h))
            aspect = longest / shortest
            if coverage > MAX_UNKNOWN_BBOX_COVERAGE:
                continue
            if fill_ratio < 0.015 and aspect < 3.0:
                continue
            score = contour_area + bbox_area * min(aspect, 6.0) * 0.08
            candidates.append((xyxy[0], xyxy[1], xyxy[2], xyxy[3], score))

        if not candidates:
            return None

        x1, y1, x2, y2, score = max(candidates, key=lambda item: item[4])
        area_ratio = ((x2 - x1) * (y2 - y1)) / max(frame_area, 1.0)
        confidence = max(0.12, min(0.39, area_ratio / max(min_area_ratio * 6.0, 1e-6)))
        return UnknownObjectCandidate((x1, y1, x2, y2), confidence, "static_contrast")
