import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QLabel

from app.ui.main_window import MainWindow
from app.ui.widgets.empty_state import EmptyState


def test_main_window_no_runtime_data_uses_safe_empty_states(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.stack.count() == 6
    assert len(window.findChildren(EmptyState)) == 4
    assert window.mapping_page is None
    assert window.capture_page is None
    assert window.settings_page is None

    labels = [label.text().casefold() for label in window.findChildren(QLabel)]
    assert not any("placeholder" in text for text in labels)
