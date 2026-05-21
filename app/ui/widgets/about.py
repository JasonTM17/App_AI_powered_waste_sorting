"""About dialog: version, model info, links."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app import __version__


class AboutDialog(QDialog):
    def __init__(self, model_class_names: dict[int, str] | None = None,
                 model_imgsz: int = 640, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Về Trash Sorter Pro")
        self.setMinimumSize(480, 360)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(12)

        title = QLabel("Trash Sorter Pro")
        title.setFont(QFont("Inter", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)

        ver = QLabel(f"version {__version__}")
        ver.setStyleSheet("color: #94A3B8;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(ver)

        info = QTextEdit()
        info.setReadOnly(True)
        info.setStyleSheet("background: #0B1220; border-radius: 8px; padding: 12px;")
        names = model_class_names or {}
        names_str = "\n".join(f"  {k}: {v}" for k, v in sorted(names.items())) or "  (no model loaded)"
        info.setPlainText(
            f"Model input size: {model_imgsz}\n"
            f"Classes ({len(names)}):\n{names_str}\n"
        )
        outer.addWidget(info, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("Đóng")
        btn_close.setObjectName("primary")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        outer.addLayout(btn_row)
