"""Empty state placeholder: centered icon + heading + sub-message."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class EmptyState(QWidget):
    def __init__(
        self, icon: str = "○", heading: str = "Chưa có dữ liệu", message: str = "", parent=None
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("color: #334155; font-size: 64px;")
        layout.addWidget(icon_label)

        head = QLabel(heading)
        head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.setFont(QFont("Inter", 16, QFont.Weight.DemiBold))
        head.setStyleSheet("color: #94A3B8;")
        layout.addWidget(head)

        if message:
            msg = QLabel(message)
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setStyleSheet("color: #64748B;")
            msg.setWordWrap(True)
            layout.addWidget(msg)
