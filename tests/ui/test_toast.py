import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QWidget

from app.ui.widgets.toast import Toast


def test_toast_constructs(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    t = Toast(parent, "Hello", level="ok", duration_ms=100)
    assert t.objectName() == "toast"


def test_toast_invalid_level_falls_back(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    t = Toast(parent, "Hi", level="unknown")
    assert t is not None
