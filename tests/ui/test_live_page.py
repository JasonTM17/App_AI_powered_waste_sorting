import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QBoxLayout

import app.ui.pages.live as live_module
from app.ui.pages.live import LivePage
from app.ui.widgets.theme import apply_theme


def test_live_page_action_controls_use_stable_equal_dimensions(qtbot):
    page = LivePage()
    qtbot.addWidget(page)

    controls = [
        page.btn_camera,
        page.btn_actuation,
        page.dispatch_mode_label,
        page.btn_pause,
        page.btn_snap,
    ]
    assert len({(control.width(), control.height()) for control in controls}) == 1

    initial_size = page.btn_actuation.size()
    page.set_camera_on(True)
    page.set_actuation_test_mode(True)
    page._toggle_pause()

    assert page.btn_camera.size() == initial_size
    assert page.btn_actuation.size() == initial_size
    assert page.btn_pause.size() == initial_size


def test_live_page_action_controls_share_same_visual_row(qtbot):
    apply_theme(QApplication.instance(), "dark")
    page = LivePage()
    qtbot.addWidget(page)
    page.resize(1255, 700)
    page.show()
    QApplication.processEvents()

    controls = [
        page.btn_camera,
        page.btn_actuation,
        page.dispatch_mode_label,
        page.btn_pause,
        page.btn_snap,
    ]

    assert {(control.geometry().top(), control.geometry().height()) for control in controls} == {
        (controls[0].geometry().top(), controls[0].geometry().height())
    }

    page.set_actuation_test_mode(True)
    page.set_uart_status(True, protocol="plain_group")
    QApplication.processEvents()

    assert {(control.geometry().top(), control.geometry().height()) for control in controls} == {
        (controls[0].geometry().top(), controls[0].geometry().height())
    }


def test_live_page_speaker_buttons_use_equal_dimensions(qtbot):
    page = LivePage()
    qtbot.addWidget(page)

    assert page.btn_hw_speaker.size() == page.btn_pc_speaker.size()


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
    assert page.btn_actuation.text() == "Dừng tự động"
    assert page.dispatch_mode_label.text() == "Chờ UART"
    assert "UART chưa kết nối" in page.warning.text()
    assert page.warning.isVisibleTo(page) is True

    page.set_uart_status(True, protocol="plain_group")
    assert page.dispatch_mode_label.text() == "Chờ khay trống"
    assert "Format: huuco / voco / taiche" in page.dispatch_status_detail.text()

    page.set_auto_sort_state("READY")
    assert page.dispatch_mode_label.text() == "Sẵn sàng"
    page.set_auto_sort_state("SORTING")
    assert page.dispatch_mode_label.text() == "Đang đổ rác"
    page.set_auto_sort_state("RETURNING")
    assert page.dispatch_mode_label.text() == "Đang về HOME"

    page.set_actuation_test_mode(False)
    assert page.btn_actuation.isChecked() is False
    assert page.btn_actuation.text() == "Bật phân loại tự động"
    assert "Chỉ nhận diện" in page.dispatch_mode_label.text()
    assert page.warning.isVisibleTo(page) is False


def test_live_page_speaker_selector_emits_and_syncs_state(qtbot):
    page = LivePage()
    qtbot.addWidget(page)

    with qtbot.waitSignal(page.speaker_output_mode_changed, timeout=500) as blocker:
        page.btn_pc_speaker.click()

    assert blocker.args == ["computer_speaker"]
    assert page.btn_pc_speaker.isChecked() is True
    assert page.btn_hw_speaker.isChecked() is False
    assert page.speaker_status.text() == ""
    assert page.speaker_status.isHidden()

    page.set_speaker_output_mode("hardware")
    assert page.btn_hw_speaker.isChecked() is True
    assert page.btn_pc_speaker.isChecked() is False
    assert page.speaker_status.text() == ""
    assert page.speaker_status.isHidden()


def test_live_page_stacks_video_and_detection_stream_when_narrow(qtbot):
    page = LivePage()
    qtbot.addWidget(page)

    page.resize(760, 720)
    page._sync_responsive_body()
    assert page._body_layout.direction() == QBoxLayout.Direction.TopToBottom
    assert page._stream_card.maximumHeight() == 260

    page.resize(1040, 720)
    page._sync_responsive_body()
    assert page._body_layout.direction() == QBoxLayout.Direction.LeftToRight
    assert page._stream_card.maximumHeight() == 16777215


def test_live_page_coalesces_same_detection_within_one_second(qtbot, monkeypatch):
    page = LivePage()
    qtbot.addWidget(page)
    ticks = iter((10.0, 10.4))
    monkeypatch.setattr(live_module.time, "monotonic", lambda: next(ticks))

    page.append_detection("Pen", 0.51, "09:32:01", "TEST OFF; Vô cơ; bin 2")
    page.append_detection("Pen", 0.56, "09:32:01", "TEST OFF; Vô cơ; bin 2")

    assert page.stream.count() == 1
    assert "0.56" in page.stream.item(0).text()
    assert "[x2]" in page.stream.item(0).text()


def test_live_page_keeps_distinct_or_later_detections(qtbot, monkeypatch):
    page = LivePage()
    qtbot.addWidget(page)
    ticks = iter((10.0, 10.2, 11.5))
    monkeypatch.setattr(live_module.time, "monotonic", lambda: next(ticks))

    page.append_detection("Pen", 0.51, "09:32:01", "route A")
    page.append_detection("Pen", 0.52, "09:32:01", "route B")
    page.append_detection("Pen", 0.53, "09:32:02", "route A")

    assert page.stream.count() == 3
