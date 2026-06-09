import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.ui.pages.live import LivePage


def test_live_page_camera_button_emits_toggle(qtbot):
    page = LivePage()
    qtbot.addWidget(page)

    with qtbot.waitSignal(page.camera_toggled, timeout=500) as blocker:
        page.btn_camera.click()

    assert blocker.args == [True]
    assert page.btn_camera.isChecked() is True


def test_live_page_warning_banner_toggles_visibility(qtbot):
    page = LivePage()
    qtbot.addWidget(page)

    page.set_warning("only one object")
    assert page.warning.isVisibleTo(page) is True
    assert page.warning.text() == "only one object"

    page.set_warning("")
    assert page.warning.isVisibleTo(page) is False


def test_live_page_actuation_button_emits_and_syncs_state(qtbot):
    page = LivePage()
    qtbot.addWidget(page)

    with qtbot.waitSignal(page.actuation_test_mode_toggled, timeout=500) as blocker:
        page.btn_actuation.click()

    assert blocker.args == [True]
    assert page.btn_actuation.isChecked() is True
    assert page.btn_actuation.text() == "Dừng gửi Arduino"

    page.set_actuation_test_mode(False)
    assert page.btn_actuation.isChecked() is False
    assert page.btn_actuation.text() == "Cho phép gửi Arduino"
    assert "Chỉ nhận diện" in page.dispatch_mode_label.text()


def test_live_page_speaker_selector_emits_and_syncs_state(qtbot):
    page = LivePage()
    qtbot.addWidget(page)

    with qtbot.waitSignal(page.speaker_output_mode_changed, timeout=500) as blocker:
        page.btn_pc_speaker.click()

    assert blocker.args == ["computer_speaker"]
    assert page.btn_pc_speaker.isChecked() is True
    assert page.btn_hw_speaker.isChecked() is False
    assert "Loa laptop" in page.speaker_status.text()

    page.set_speaker_output_mode("hardware")
    assert page.btn_hw_speaker.isChecked() is True
    assert page.btn_pc_speaker.isChecked() is False
    assert "Loa laptop" in page.speaker_status.text()
