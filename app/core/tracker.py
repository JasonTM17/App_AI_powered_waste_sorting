"""Lightweight IoU-based tracker for per-object UART dispatch."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.core.events import TrackedDetection
from app.core.three_bin_classifier import parse_three_bin_class_name
from app.core.waste_categories import category_for_known_class


def _iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    x1 = max(ax1, bx1)
    y1 = max(ay1, by1)
    x2 = min(ax2, bx2)
    y2 = min(ay2, by2)
    iw = max(0, x2 - x1)
    ih = max(0, y2 - y1)
    inter = iw * ih
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _area(box) -> float:
    x1, y1, x2, y2 = box
    return float(max(0, x2 - x1) * max(0, y2 - y1))


def _intersection_area(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    iw = max(0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0, min(ay2, by2) - max(ay1, by1))
    return float(iw * ih)


def _center_distance_ratio(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    acx = (ax1 + ax2) / 2.0
    acy = (ay1 + ay2) / 2.0
    bcx = (bx1 + bx2) / 2.0
    bcy = (by1 + by2) / 2.0
    span = max(
        abs(ax2 - ax1),
        abs(ay2 - ay1),
        abs(bx2 - bx1),
        abs(by2 - by1),
        1.0,
    )
    return (((acx - bcx) ** 2 + (acy - bcy) ** 2) ** 0.5) / span


def _tracking_match_score(a, b, *, iou_threshold: float) -> float:
    iou = _iou(a, b)
    if iou >= iou_threshold:
        return 1.0 + iou
    smaller = min(_area(a), _area(b))
    if smaller <= 0:
        return 0.0
    smaller_overlap = _intersection_area(a, b) / smaller
    center_ratio = _center_distance_ratio(a, b)
    if smaller_overlap >= 0.55 and center_ratio <= 0.65:
        return 0.5 + smaller_overlap - (center_ratio * 0.1)
    return 0.0


@dataclass
class _Track:
    track_id: int
    cls_id: int
    label_signature: str
    route_signature: str
    xyxy: tuple
    age: int = 0
    stable_frames: int = 1
    first_seen_ts: float = field(default_factory=time.time)


class Tracker:
    def __init__(self, iou_threshold=0.3, max_age=30):
        self._iou_th = iou_threshold
        self._max_age = max_age
        self._next_id = 1
        self._tracks: dict[int, _Track] = {}
        self._emitted: set[int] = set()

    def update(self, detections):
        for t in self._tracks.values():
            t.age += 1
        out = []
        matched_ids: set[int] = set()
        for det in detections:
            best_id = None
            best_score = 0.0
            for tid, t in self._tracks.items():
                if tid in matched_ids:
                    continue
                score = _tracking_match_score(
                    det.xyxy,
                    t.xyxy,
                    iou_threshold=self._iou_th,
                )
                if score > best_score:
                    best_score = score
                    best_id = tid
            if best_id is None:
                tid = self._next_id
                self._next_id += 1
                self._tracks[tid] = _Track(
                    track_id=tid,
                    cls_id=det.cls_id,
                    label_signature=_label_signature(det),
                    route_signature=_route_family(det.cls_name),
                    xyxy=det.xyxy,
                )
                t = self._tracks[tid]
            else:
                t = self._tracks[best_id]
                t.age = 0
                label_signature = _label_signature(det)
                route_signature = _route_family(det.cls_name)
                if route_signature != t.route_signature:
                    # A different three-bin route at the same tray position is
                    # a new sortable object, not the already-emitted object.
                    self._emitted.discard(t.track_id)
                if label_signature == t.label_signature:
                    t.stable_frames += 1
                else:
                    t.stable_frames = 1
                    t.label_signature = label_signature
                t.route_signature = route_signature
                t.cls_id = det.cls_id
                t.xyxy = det.xyxy
            matched_ids.add(t.track_id)
            out.append(
                TrackedDetection(
                    track_id=t.track_id,
                    detection=det,
                    stable_frames=t.stable_frames,
                    first_seen_ts=t.first_seen_ts,
                )
            )
        dead = [tid for tid, t in self._tracks.items() if t.age > self._max_age]
        for tid in dead:
            self._tracks.pop(tid, None)
            self._emitted.discard(tid)
        return out

    def should_emit(self, track_id):
        return track_id not in self._emitted

    def mark_emitted(self, track_id):
        self._emitted.add(track_id)

    def clear_active(self) -> None:
        self._tracks.clear()
        self._emitted.clear()

    def reset(self):
        self._tracks.clear()
        self._emitted.clear()
        self._next_id = 1


def _label_signature(detection) -> str:
    operator_label = str(detection.operator_label or "").strip().casefold()
    return f"{_route_family(detection.cls_name)}|{detection.cls_name}|{operator_label}"


def _route_family(class_name: str) -> str:
    command = parse_three_bin_class_name(class_name)
    if command is not None:
        return f"route:{command}"
    category = category_for_known_class(class_name)
    if category is not None:
        return f"route:{category.code}"
    return f"class:{class_name}"
