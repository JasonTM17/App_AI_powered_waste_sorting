import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.ui.widgets.splash import Splash


def test_splash_constructs(qtbot):
    s = Splash("Hi")
    assert s.size().width() > 0


def test_splash_set_message(qtbot):
    s = Splash()
    s.set_message("Loading…")
    assert s.message().endswith("Loading…")
