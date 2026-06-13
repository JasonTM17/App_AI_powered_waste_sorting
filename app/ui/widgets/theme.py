"""Theme loader: read QSS file, apply to QApplication."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

QSS_DIR = Path(__file__).parent.parent / "resources" / "qss"


def apply_theme(app: QApplication, theme: str = "dark") -> None:
    normalized = str(theme or "dark").strip().lower()
    if normalized not in {"dark", "light"}:
        normalized = "dark"
    qss_file = QSS_DIR / f"{normalized}.qss"
    if not qss_file.exists():
        qss_file = QSS_DIR / "dark.qss"
        normalized = "dark"
    app.setProperty("trashSorterTheme", normalized)
    app.setStyleSheet(qss_file.read_text(encoding="utf-8"))
    for widget in app.allWidgets():
        widget.setProperty("trashSorterTheme", normalized)
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()
