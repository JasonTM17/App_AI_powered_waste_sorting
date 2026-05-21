"""Toast notification: slide-in top-right, auto-dismiss."""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QTimer,
)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

_LEVEL_COLORS = {
    "info": "#3B82F6",
    "ok": "#10B981",
    "warn": "#F59E0B",
    "error": "#EF4444",
}


class Toast(QFrame):
    def __init__(
        self,
        parent: QWidget,
        message: str,
        level: str = "info",
        duration_ms: int = 4000,
    ):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setStyleSheet(
            "#toast { background: #111A2E; border: 1px solid rgba(255,255,255,0.1);"
            " border-radius: 8px; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {_LEVEL_COLORS.get(level, '#3B82F6')}; font-size: 16px;"
        )
        layout.addWidget(dot)

        msg = QLabel(message)
        msg.setStyleSheet("color: #F1F5F9;")
        layout.addWidget(msg)

        self.adjustSize()
        self._duration = duration_ms

    def show_at(self, anchor_topright: QPoint) -> None:
        end_x = anchor_topright.x() - self.width() - 16
        end_y = anchor_topright.y() + 16
        start = QPoint(anchor_topright.x() + 20, end_y)
        self.move(start)
        self.show()
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(220)
        anim.setStartValue(start)
        anim.setEndValue(QPoint(end_x, end_y))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        QTimer.singleShot(self._duration, self.close)
