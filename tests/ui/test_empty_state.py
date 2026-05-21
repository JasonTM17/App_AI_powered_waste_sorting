import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.ui.widgets.empty_state import EmptyState


def test_empty_state_constructs(qtbot):
    e = EmptyState("⚙", "Cài đặt", "Chưa có dữ liệu")
    qtbot.addWidget(e)
    assert e is not None


def test_empty_state_no_message(qtbot):
    e = EmptyState()
    qtbot.addWidget(e)
    assert e is not None
