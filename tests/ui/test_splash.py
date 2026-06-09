import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.ui.widgets.splash import SPLASH_TAGLINE, SPLASH_TITLE, SPLASH_VERSION, Splash


def test_splash_constructs(qtbot):
    s = Splash("Hi")
    assert s.size().width() > 0


def test_splash_set_message(qtbot):
    s = Splash()
    s.set_message("Loading…")
    assert s.message().endswith("Loading…")


def test_splash_brand_text_contract():
    assert SPLASH_TITLE == "Trash Sorter Pro"
    assert SPLASH_TAGLINE == "Phân loại rác bằng AI"
    assert SPLASH_VERSION == "v1.0.0"
