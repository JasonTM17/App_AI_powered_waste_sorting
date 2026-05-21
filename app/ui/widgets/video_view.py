"""Video display widget with bbox overlay (paintEvent based)."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.core.events import Detection


def _conf_color(conf: float) -> QColor:
    if conf >= 0.8:
        return QColor("#10B981")
    if conf >= 0.5:
        return QColor("#F59E0B")
    return QColor("#EF4444")


class VideoView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(640, 360)
        self._pixmap: QPixmap | None = None
        self._frame_w = 0
        self._frame_h = 0
        self._detections: list[Detection] = []
        self.setStyleSheet("background: #000;")

    def set_frame(self, frame_bgr: np.ndarray) -> None:
        h, w, _ = frame_bgr.shape
        rgb = np.ascontiguousarray(frame_bgr[:, :, ::-1])
        img = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(img.copy())
        self._frame_w, self._frame_h = w, h
        self.update()

    def set_detections(self, detections: list[Detection]) -> None:
        self._detections = detections
        self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._pixmap is None:
            p.fillRect(self.rect(), QColor("#000"))
            return
        target = self.rect()
        scaled = self._pixmap.scaled(
            target.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (target.width() - scaled.width()) // 2
        y = (target.height() - scaled.height()) // 2
        p.drawPixmap(x, y, scaled)
        if self._frame_w and self._frame_h:
            sx = scaled.width() / self._frame_w
            sy = scaled.height() / self._frame_h
            font = QFont("Inter", 10, QFont.Weight.Bold)
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
                p.setPen(QColor("#0B1220"))
                p.drawText(rx + 6, ry - 4, label)
