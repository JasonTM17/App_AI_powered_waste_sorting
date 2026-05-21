import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.ui.widgets.about import AboutDialog


def test_about_constructs(qtbot):
    dlg = AboutDialog({0: "paper", 1: "plastic"}, 640)
    qtbot.addWidget(dlg)
    assert "Trash Sorter Pro" in dlg.windowTitle()


def test_about_no_model(qtbot):
    dlg = AboutDialog(None, 640)
    qtbot.addWidget(dlg)
    assert dlg is not None
