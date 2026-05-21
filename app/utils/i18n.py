"""Minimal i18n stub: load .qm if present, fallback to English."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTranslator
from PySide6.QtWidgets import QApplication

I18N_DIR = Path(__file__).parent.parent / "ui" / "resources" / "i18n"


def install_translator(app: QApplication, language: str = "vi") -> QTranslator | None:
    qm = I18N_DIR / f"{language}.qm"
    if not qm.exists():
        return None
    tr = QTranslator()
    if tr.load(str(qm)):
        app.installTranslator(tr)
        return tr
    return None
