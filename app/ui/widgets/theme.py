"""Theme loader: read QSS file, apply to QApplication."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

QSS_DIR = Path(__file__).parent.parent / "resources" / "qss"


def apply_theme(app: QApplication, theme: str = "dark") -> None:
    qss_file = QSS_DIR / f"{theme}.qss"
    if not qss_file.exists():
        qss_file = QSS_DIR / "dark.qss"
    app.setStyleSheet(qss_file.read_text(encoding="utf-8"))
