"""Video display widget with bbox overlay (paintEvent based)."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.core.events import Detection


def _conf_color(conf: float) -> QColor:
    if conf >= 0.8:
        return QColor("#4EDEA3")
    if conf >= 0.5:
        return QColor("#F59E0B")
    return QColor("#F43F5E")


class VideoView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(640, 360)
        self._pixmap: QPixmap | None = None
        self._scaled: QPixmap | None = None
        self._scaled_for_size = (0, 0)
        self._frame_w = 0
        self._frame_h = 0
        self._detections: list[Detection] = []
        self.setStyleSheet(
            "background: #060E20; border: 1px solid rgba(255,255,255,0.06);"
            " border-radius: 12px;"
        )

    def set_frame(self, frame_bgr: np.ndarray) -> None:
        h, w, _ = frame_bgr.shape
        rgb = np.ascontiguousarray(frame_bgr[:, :, ::-1])
        img = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(img.copy())
        self._frame_w, self._frame_h = w, h
        self._scaled = None  # invalidate cache
        # detections also arrive with frame; trigger one repaint, not two
        # (caller should call set_detections before set_frame OR we accept
        # the slightly stale boxes for one frame — better than 2x repaint)

    def set_detections(self, detections: list[Detection]) -> None:
        self._detections = detections
        self.update()

    def resizeEvent(self, ev) -> None:  # noqa: N802
        self._scaled = None
        super().resizeEvent(ev)

    def _ensure_scaled(self) -> QPixmap | None:
        if self._pixmap is None:
            return None
        size = (self.width(), self.height())
        if self._scaled is not None and self._scaled_for_size == size:
            return self._scaled
        self._scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self._scaled_for_size = size
        return self._scaled

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        scaled = self._ensure_scaled()
        if scaled is None:
            p.fillRect(self.rect(), QColor("#060E20"))
            return
        target = self.rect()
        x = (target.width() - scaled.width()) // 2
        y = (target.height() - scaled.height()) // 2
        p.drawPixmap(x, y, scaled)
        if self._frame_w and self._frame_h and self._detections:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            sx = scaled.width() / self._frame_w
            sy = scaled.height() / self._frame_h
            font = QFont("Consolas", 10, QFont.Weight.Bold)
            p.setFont(font)
            for d in self._detections:
                x1, y1, x2, y2 = d.xyxy
                rx = int(x + x1 * sx)
                ry = int(y + y1 * sy)
                rw = int((x2 - x1) * sx)
                rh = int((y2 - y1) * sy)
                color = _conf_color(d.conf)
                pen = QPen(color)
                pen.setWidth(2)
                p.setPen(pen)
                p.drawRoundedRect(rx, ry, rw, rh, 4, 4)
                label = f"{d.cls_name} {d.conf:.2f}"
                metrics = p.fontMetrics()
                tw = metrics.horizontalAdvance(label) + 12
                th = metrics.height() + 4
                p.fillRect(rx, ry - th, tw, th, color)
                p.setPen(QColor("#002113"))
                p.drawText(rx + 6, ry - 4, label)
