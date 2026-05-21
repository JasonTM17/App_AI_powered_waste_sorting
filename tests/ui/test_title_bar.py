import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.ui.widgets.title_bar import TitleBar


def test_titlebar_has_buttons(qtbot):
    bar = TitleBar(title="Test App")
    qtbot.addWidget(bar)
    assert bar.btn_min is not None
    assert bar.btn_max is not None
    assert bar.btn_close is not None
    assert "Test App" in bar.label.text()


def test_titlebar_signals_emit(qtbot):
    bar = TitleBar(title="X")
    qtbot.addWidget(bar)
    with qtbot.waitSignal(bar.minimize_requested, timeout=500):
        bar.btn_min.click()
    with qtbot.waitSignal(bar.close_requested, timeout=500):
        bar.btn_close.click()
