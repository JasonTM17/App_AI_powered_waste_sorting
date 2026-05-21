import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app.ui.widgets.tray import TrayIcon


def test_tray_constructs(qtbot):
    from PySide6.QtWidgets import QSystemTrayIcon
    if not QSystemTrayIcon.isSystemTrayAvailable():
        pytest.skip("system tray not available in this environment")
    t = TrayIcon()
    assert t.toolTip() == "Trash Sorter Pro"
    assert t.contextMenu() is not None
