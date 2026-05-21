"""Splash screen shown during model loading."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen

from app import __version__
from app.utils.paths import resource_path


def _make_splash_pixmap(width: int = 520, height: int = 320) -> QPixmap:
    pix = QPixmap(width, height)
    pix.fill(QColor("#0B1220"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # subtle accent bar at top
    painter.fillRect(0, 0, width, 4, QColor("#10B981"))

    # logo
    logo_path = resource_path("app/ui/resources/icons/logo.svg")
    if logo_path.exists():
        icon = QIcon(str(logo_path))
        logo_size = 88
        logo_pix = icon.pixmap(logo_size, logo_size)
        painter.drawPixmap(
            (width - logo_size) // 2, 56, logo_pix
        )

    # title
    painter.setPen(QColor("#F1F5F9"))
    painter.setFont(QFont("Inter", 24, QFont.Weight.Bold))
    painter.drawText(
        pix.rect().adjusted(0, 60, 0, 60),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
        "Trash Sorter Pro",
    )

    # tagline
    painter.setPen(QColor("#10B981"))
    painter.setFont(QFont("Inter", 12, QFont.Weight.DemiBold))
    painter.drawText(
        pix.rect().adjusted(0, 92, 0, 92),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
        "AI Phân loại rác thông minh",
    )

    # version
    painter.setPen(QColor("#64748B"))
    painter.setFont(QFont("Inter", 10))
    painter.drawText(
        pix.rect().adjusted(0, 0, 0, -16),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
        f"v{__version__}",
    )

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
