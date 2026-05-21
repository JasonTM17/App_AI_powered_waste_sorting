"""Splash screen shown during model loading."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen


def _make_splash_pixmap(width: int = 480, height: int = 280) -> QPixmap:
    pix = QPixmap(width, height)
    pix.fill(QColor("#0B1220"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("#10B981"))
    title_font = QFont("Inter", 28, QFont.Weight.Bold)
    painter.setFont(title_font)
    painter.drawText(pix.rect().adjusted(0, -30, 0, -30), Qt.AlignmentFlag.AlignCenter, "Trash Sorter Pro")
    painter.setPen(QColor("#94A3B8"))
    sub_font = QFont("Inter", 12)
    painter.setFont(sub_font)
    painter.drawText(pix.rect().adjusted(0, 30, 0, 30), Qt.AlignmentFlag.AlignCenter, "v2.0.0")
    painter.end()
    return pix


class Splash(QSplashScreen):
    def __init__(self, message: str = "Loading model…"):
        super().__init__(_make_splash_pixmap(), Qt.WindowType.WindowStaysOnTopHint)
        self.set_message(message)

    def set_message(self, msg: str) -> None:
        self.showMessage(
            msg,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor("#94A3B8"),
        )
