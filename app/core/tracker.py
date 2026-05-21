"""Lightweight IoU-based tracker for per-object UART dispatch."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.core.events import TrackedDetection


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


@dataclass
class _Track:
    track_id: int
    cls_id: int
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
        for det in detections:
            best_id = None
            best_iou = self._iou_th
            for tid, t in self._tracks.items():
                if t.cls_id != det.cls_id:
                    continue
                score = _iou(det.xyxy, t.xyxy)
                if score > best_iou:
                    best_iou = score
                    best_id = tid
            if best_id is None:
                tid = self._next_id
                self._next_id += 1
                self._tracks[tid] = _Track(track_id=tid, cls_id=det.cls_id, xyxy=det.xyxy)
                t = self._tracks[tid]
            else:
                t = self._tracks[best_id]
                t.age = 0
                t.stable_frames += 1
                t.xyxy = det.xyxy
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
