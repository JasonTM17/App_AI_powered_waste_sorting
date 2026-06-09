"""Splash screen shown during model loading."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen

from app import __version__
from app.ui.brand_assets import brand_mark_path

SPLASH_TITLE = "Trash Sorter Pro"
SPLASH_TAGLINE = "Phân loại rác bằng AI"
SPLASH_VERSION = f"v{__version__}"


def _make_splash_pixmap(width: int = 520, height: int = 320) -> QPixmap:
    pix = QPixmap(width, height)
    pix.fill(QColor("#0B1220"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.fillRect(0, 0, width, 4, QColor("#10B981"))
    painter.setPen(QColor(20, 184, 166, 70))
    painter.drawRoundedRect(126, 50, 268, 206, 18, 18)
    painter.setPen(QColor(148, 163, 184, 45))
    painter.drawLine(154, 229, width - 154, 229)

    logo_size = 92
    logo_y = 44
    logo_path = brand_mark_path()
    if logo_path.exists():
        logo_pix = QIcon(str(logo_path)).pixmap(logo_size, logo_size)
        painter.drawPixmap((width - logo_size) // 2, logo_y, logo_pix)

    painter.setPen(QColor("#F8FAFC"))
    painter.setFont(QFont("Segoe UI", 27, QFont.Weight.Bold))
    painter.drawText(
        QRect(0, logo_y + logo_size + 20, width, 40),
        Qt.AlignmentFlag.AlignCenter,
        SPLASH_TITLE,
    )

    painter.setPen(QColor("#34D399"))
    painter.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
    painter.drawText(
        QRect(0, logo_y + logo_size + 60, width, 26),
        Qt.AlignmentFlag.AlignCenter,
        SPLASH_TAGLINE,
    )

    painter.setPen(QColor("#94A3B8"))
    painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
    painter.drawText(
        QRect(0, logo_y + logo_size + 90, width, 22),
        Qt.AlignmentFlag.AlignCenter,
        SPLASH_VERSION,
    )

    painter.end()
    return pix


class Splash(QSplashScreen):
    def __init__(self, message: str = "Loading model..."):
        super().__init__(_make_splash_pixmap(), Qt.WindowType.WindowStaysOnTopHint)
        self.set_message(message)

    def set_message(self, msg: str) -> None:
        self.showMessage(
            msg,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor("#CBD5E1"),
        )
