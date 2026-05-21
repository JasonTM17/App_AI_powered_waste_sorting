"""Pipeline orchestrator: frame -> infer -> track -> uart -> history."""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.config import AppConfig
from app.core.history import HistoryService
from app.core.tracker import Tracker
from app.utils.logging import logger


def _make_thumbnail(frame_bgr: np.ndarray, max_size=(100, 75)) -> bytes:
    rgb = frame_bgr[:, :, ::-1]
    img = Image.fromarray(rgb)
    img.thumbnail(max_size)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


class Pipeline:
    def __init__(self, cfg: AppConfig, engine, uart, history_db: Path):
        self.cfg = cfg
        self.engine = engine
        self.uart = uart
        self.tracker = Tracker(iou_threshold=0.3, max_age=30)
        self.history = HistoryService(history_db)
        self._mapping = {m.class_name: m for m in cfg.mappings if m.enabled}
        self._track_to_row: dict[int, int] = {}

    def update_mappings(self, mappings):
        self._mapping = {m.class_name: m for m in mappings if m.enabled}

    def _in_roi(self, xyxy):
        roi = self.cfg.roi
        if not roi.enabled or roi.width == 0 or roi.height == 0:
            return True
        x1, y1, x2, y2 = xyxy
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        return roi.x <= cx <= roi.x + roi.width and roi.y <= cy <= roi.y + roi.height

    def process_frame(self, frame_bgr: np.ndarray, ts: datetime):
        raw = self.engine.predict(frame_bgr)
        filtered = [d for d in raw if d.conf >= self.cfg.model.conf_threshold and self._in_roi(d.xyxy)]
        tracked = self.tracker.update(filtered)
        detections_for_render = [t.detection for t in tracked]
        for t in tracked:
            if not self.tracker.should_emit(t.track_id):
                continue
            mapping = self._mapping.get(t.detection.cls_name)
            if mapping is None:
                continue
            self.tracker.mark_emitted(t.track_id)
            thumb = _make_thumbnail(frame_bgr)
            row_id = self.history.insert(
                track_id=t.track_id, ts=ts,
                cls_id=t.detection.cls_id, cls_name=t.detection.cls_name,
                conf=t.detection.conf, bbox=t.detection.xyxy,
                thumbnail=thumb, uart_command=mapping.command, ack_status="pending",
            )
            self._track_to_row[t.track_id] = row_id
            self.uart.send(track_id=t.track_id, command=mapping.command, conf=t.detection.conf)
            logger.info("dispatch track={} cls={} cmd={} conf={:.2f}",
                        t.track_id, t.detection.cls_name, mapping.command, t.detection.conf)
        return detections_for_render

    def on_ack(self, track_id: int, command: str, status: str, rtt_ms):
        row_id = self._track_to_row.pop(track_id, None)
        if row_id is None:
            return
        self.history.update_ack(row_id, status=status, rtt_ms=rtt_ms)

    def close(self):
        self.history.close()
