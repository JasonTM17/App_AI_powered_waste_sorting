"""About dialog: branded hero + model info."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app import __version__
from app.ui.brand_assets import brand_mark_path


class AboutDialog(QDialog):
    def __init__(
        self, model_class_names: dict[int, str] | None = None, model_imgsz: int = 640, parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Về Trash Sorter Pro")
        self.setMinimumSize(520, 460)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 20)
        outer.setSpacing(10)

        # hero row: logo + title + version
        hero = QHBoxLayout()
        hero.setSpacing(16)
        logo = QLabel()
        logo_path = brand_mark_path()
        if logo_path.exists():
            logo.setPixmap(QIcon(str(logo_path)).pixmap(QSize(64, 64)))
        logo.setFixedSize(72, 72)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.addWidget(logo)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title = QLabel("Trash Sorter Pro")
        title.setFont(QFont("Inter", 20, QFont.Weight.Bold))
        text_col.addWidget(title)
        tagline = QLabel("AI Phân loại rác thông minh")
        tagline.setStyleSheet("color: #10B981; font-size: 13px; font-weight: 600;")
        text_col.addWidget(tagline)
        ver = QLabel(f"version {__version__}")
        ver.setStyleSheet("color: #94A3B8; font-size: 12px;")
        text_col.addWidget(ver)
        text_col.addStretch()
        hero.addLayout(text_col, 1)
        outer.addLayout(hero)

        names = model_class_names or {}
        meta = QLabel(
            f"<span style='color:#94A3B8'>Model:</span> "
            f"<span style='color:#F1F5F9'>YOLOv8 · "
            f"{len(names)} lớp · input {model_imgsz}px</span><br>"
            f"<span style='color:#94A3B8'>Dataset:</span> "
            f"<span style='color:#F1F5F9'>Roboflow projectverba/yolo-waste-detection</span>"
        )
        meta.setTextFormat(Qt.TextFormat.RichText)
        meta.setStyleSheet(
            "background: #0B1220; border-radius: 8px;"
            " padding: 12px 14px; font-size: 12px;"
        )
        outer.addWidget(meta)

        info = QTextEdit()
        info.setReadOnly(True)
        info.setStyleSheet(
            "background: #0B1220; border-radius: 8px; padding: 12px;"
            " font-family: 'Consolas'; font-size: 12px;"
        )
        names_str = (
            "\n".join(f"  {k:>2}: {v}" for k, v in sorted(names.items()))
            or "  (no model loaded)"
        )
        info.setPlainText(f"Classes ({len(names)}):\n{names_str}\n")
        outer.addWidget(info, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("Đóng")
        btn_close.setObjectName("primary")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        outer.addLayout(btn_row)
