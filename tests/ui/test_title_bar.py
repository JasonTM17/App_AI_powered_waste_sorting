import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.ui.widgets.title_bar import TitleBar


def test_titlebar_has_buttons(qtbot):
    bar = TitleBar(title="Test App")
    qtbot.addWidget(bar)
    assert bar.btn_min is not None
    assert bar.btn_max is not None
    assert bar.btn_close is not None
    assert bar.btn_web is not None
    assert "Test App" in bar.label.text()


def test_titlebar_signals_emit(qtbot):
    bar = TitleBar(title="X")
    qtbot.addWidget(bar)
    with qtbot.waitSignal(bar.minimize_requested, timeout=500):
        bar.btn_min.click()
    with qtbot.waitSignal(bar.close_requested, timeout=500):
        bar.btn_close.click()
    with qtbot.waitSignal(bar.web_requested, timeout=500):
        bar.btn_web.click()


def test_titlebar_camera_button_emits_toggle(qtbot):
    bar = TitleBar(title="X")
    qtbot.addWidget(bar)

    with qtbot.waitSignal(bar.camera_toggled, timeout=500) as blocker:
        bar.btn_camera.click()

    assert blocker.args == [True]


def test_titlebar_compact_keeps_actions_accessible(qtbot):
    bar = TitleBar(title="X")
    qtbot.addWidget(bar)

    bar.set_compact(True)

    assert bar.btn_web.text() == ""
    assert bar.btn_camera.text() == ""
    assert bar.btn_web.toolTip() == "Mở Web"
    assert bar.btn_camera.toolTip() == "Bật camera"
    assert bar.btn_web.maximumWidth() == 44
    assert bar.btn_camera.maximumWidth() == 44

    with qtbot.waitSignal(bar.web_requested, timeout=500):
        bar.btn_web.click()

    bar.set_camera_on(True)
    assert bar.btn_camera.text() == ""
    assert bar.btn_camera.toolTip() == "Tắt camera"

    bar.set_compact(False)
    assert bar.btn_web.text() == "Mở Web"
    assert bar.btn_camera.text() == "Tắt camera"
