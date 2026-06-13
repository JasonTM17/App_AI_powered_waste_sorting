import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QLabel

from app.ui.widgets.empty_state import EmptyState


def test_empty_state_constructs(qtbot):
    e = EmptyState("⚙", "Cài đặt", "Chưa có dữ liệu")
    qtbot.addWidget(e)
    labels = e.findChildren(QLabel)
    assert len(labels) == 3
    assert labels[0].text() == "⚙"
    assert labels[1].text() == "Cài đặt"
    assert labels[2].text() == "Chưa có dữ liệu"


def test_empty_state_no_message(qtbot):
    e = EmptyState()
    qtbot.addWidget(e)
    labels = e.findChildren(QLabel)
    assert len(labels) == 2
    assert labels[0].text() == "○"
    assert labels[1].text() == "Chưa có dữ liệu"
