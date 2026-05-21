import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.ui.widgets.skeleton import Skeleton


def test_skeleton_constructs(qtbot):
    s = Skeleton()
    qtbot.addWidget(s)
    assert s.minimumHeight() == 20


def test_skeleton_offset_setter(qtbot):
    s = Skeleton()
    qtbot.addWidget(s)
    s.set_offset(0.5)
    assert abs(s.get_offset() - 0.5) < 1e-6
