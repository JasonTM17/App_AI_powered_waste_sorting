"""Shimmer skeleton placeholder widget."""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget


class Skeleton(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(20)
        self._offset = 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(1200)
        self._anim.setLoopCount(-1)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._anim.start()

    def get_offset(self) -> float:
        return self._offset

    def set_offset(self, v: float) -> None:
        self._offset = v
        self.update()

    offset = Property(float, get_offset, set_offset)

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        p.setBrush(QColor("#152038"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        gradient = QLinearGradient(rect.topLeft(), rect.topRight())
        c0 = QColor(255, 255, 255, 0)
        c1 = QColor(255, 255, 255, 30)
        x = self._offset
        gradient.setColorAt(max(0.0, x - 0.2), c0)
        gradient.setColorAt(min(1.0, x), c1)
        gradient.setColorAt(min(1.0, x + 0.2), c0)
        p.setBrush(gradient)
        p.drawRoundedRect(rect, 6, 6)
