import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QPushButton,
    QSizePolicy,
)

from app.core.config import AppConfig
from app.ui.pages.settings import SettingsPage


def _is_descendant(widget, ancestor) -> bool:
    parent = widget.parent()
    while parent is not None:
        if parent is ancestor:
            return True
        parent = parent.parent()
    return False


def test_settings_emits_config_on_save(qtbot):
    cfg = AppConfig()
    page = SettingsPage(cfg)
    qtbot.addWidget(page)
    captured = []
    page.config_saved.connect(lambda c: captured.append(c))
    page.mdl_conf.setValue(50)
    page._save()
    assert captured
    assert abs(captured[0].model.conf_threshold - 0.5) < 1e-6


def test_settings_collect_keeps_empty_when_no_usb(qtbot):
    cfg = AppConfig()
    page = SettingsPage(cfg)
    qtbot.addWidget(page)
    page.cam_source.clear()
    page.cam_source.addItem("Chưa có camera USB", "")
    page.cam_source.setCurrentIndex(0)
    out = page._collect()
    assert out.camera.source == ""
    assert not page.btn_test_cam.isEnabled()


def test_settings_collect_uses_camera_item_data(qtbot):
    cfg = AppConfig()
    page = SettingsPage(cfg)
    qtbot.addWidget(page)
    page.cam_source.clear()
    page.cam_source.addItem("1 (DSHOW) - USB Camera", "1")
    page.cam_source.setCurrentIndex(0)
    out = page._collect()
    assert out.camera.source == "1"
    assert out.camera.rotation == 0


def test_settings_collect_uses_camera_rotation(qtbot):
    cfg = AppConfig()
    page = SettingsPage(cfg)
    qtbot.addWidget(page)
    page.cam_rotation.setCurrentIndex(page.cam_rotation.findData(270))
    out = page._collect()
    assert out.camera.rotation == 270


def test_settings_camera_selector_expands_and_hint_does_not_overlap(qtbot):
    page = SettingsPage(AppConfig())
    qtbot.addWidget(page)
    page.resize(1000, 4000)
    page.cam_hint.setText(
        "Đã tìm thấy camera USB đọc được frame. "
        "Chọn dòng USB rồi bấm Test camera."
    )
    page.show()
    QApplication.processEvents()

    assert (
        page.cam_source.sizePolicy().horizontalPolicy()
        == QSizePolicy.Policy.Expanding
    )
    assert page.cam_source.width() >= 500
    hint_bottom = page.cam_hint.mapTo(page, QPoint(0, page.cam_hint.height())).y()
    width_top = page.cam_w.mapTo(page, QPoint(0, 0)).y()
    assert hint_bottom <= width_top


def test_settings_collect_saves_roi_fields(qtbot):
    cfg = AppConfig()
    page = SettingsPage(cfg)
    qtbot.addWidget(page)
    page.roi_enabled.setChecked(True)
    page.roi_x.setValue(11)
    page.roi_y.setValue(22)
    page.roi_w.setValue(333)
    page.roi_h.setValue(444)

    out = page._collect()

    assert out.roi.enabled is True
    assert (out.roi.x, out.roi.y, out.roi.width, out.roi.height) == (11, 22, 333, 444)


def test_settings_collect_keeps_empty_uart_without_usb(qtbot):
    cfg = AppConfig()
    page = SettingsPage(cfg)
    qtbot.addWidget(page)
    page.uart_port.clear()
    page.uart_port.addItem("Chưa thấy cổng USB/Arduino", "")
    page.uart_port.setCurrentIndex(0)
    page.btn_test_uart.setEnabled(False)

    out = page._collect()

    assert out.uart.port == ""
    assert not page.btn_test_uart.isEnabled()


def test_settings_audio_output_defaults_to_hardware(qtbot):
    cfg = AppConfig()
    page = SettingsPage(cfg)
    qtbot.addWidget(page)

    out = page._collect()

    assert page.audio_section.output_mode() == "hardware"
    assert page.audio_section.hardware_button.isChecked() is True
    assert page.audio_section.hardware_button.text() == "Loa phần cứng"
    assert page.audio_section.computer_button.text() == "Loa laptop"
    assert page.audio_section.status_label.text() == ""
    assert page.audio_section.status_label.isHidden()
    assert out.speaker.output_mode == "hardware"
    assert out.speaker.enabled is False
    assert out.speaker.voice_gender == "female"
    assert not page.audio_section.speaker_cooldown.isEnabled()
    assert page.audio_section.female_voice_button.isEnabled()
    assert page.audio_section.male_voice_button.isEnabled()


def test_settings_numeric_inputs_ignore_wheel_and_hide_step_buttons(qtbot):
    page = SettingsPage(AppConfig())
    qtbot.addWidget(page)
    starting_baud = page.uart_baud.currentText()
    starting_timeout = page.uart_timeout.value()

    def send_wheel(widget):
        event = QWheelEvent(
            QPointF(10, 10),
            QPointF(10, 10),
            QPoint(),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(widget, event)

    send_wheel(page.uart_baud)
    send_wheel(page.uart_timeout)

    assert page.uart_baud.currentText() == starting_baud
    assert page.uart_timeout.value() == starting_timeout
    assert (
        page.uart_timeout.buttonSymbols()
        == QAbstractSpinBox.ButtonSymbols.NoButtons
    )


def test_settings_collect_saves_computer_speaker_output(qtbot):
    cfg = AppConfig()
    page = SettingsPage(cfg)
    qtbot.addWidget(page)
    page.audio_section.set_output_mode("computer_speaker")
    page.audio_section.set_voice_gender("male")
    page.audio_section.speaker_cooldown.setValue(4.5)

    out = page._collect()

    assert out.speaker.output_mode == "computer_speaker"
    assert out.speaker.enabled is True
    assert out.speaker.voice_gender == "male"
    assert out.speaker.cooldown_seconds == 4.5
    assert page.audio_section.computer_button.isChecked() is True
    assert page.audio_section.speaker_cooldown.isEnabled()
    assert page.audio_section.male_voice_button.isChecked() is True
    assert page.audio_section.male_voice_button.isEnabled()


def test_settings_voice_test_buttons_emit_requested_command(qtbot):
    cfg = AppConfig()
    page = SettingsPage(cfg)
    qtbot.addWidget(page)
    captured = []
    page.test_voice_requested.connect(
        lambda command, mode, gender: captured.append((command, mode, gender))
    )
    button = next(btn for btn in page.audio_section.findChildren(QPushButton) if btn.text() == "Test hữu cơ")

    button.click()

    assert captured == [("sort_O", "hardware", "female")]


def test_settings_voice_test_buttons_cover_all_audio_events(qtbot):
    cfg = AppConfig()
    page = SettingsPage(cfg)
    qtbot.addWidget(page)
    captured = []
    page.test_voice_requested.connect(
        lambda command, mode, gender: captured.append((command, mode, gender))
    )
    labels = {
        "Test khởi động": "startup",
        "Test hữu cơ": "sort_O",
        "Test vô cơ": "sort_R",
        "Test tái chế": "sort_I",
        "Test hữu cơ đầy": "bin_full_O",
        "Test vô cơ đầy": "bin_full_R",
        "Test tái chế đầy": "bin_full_I",
        "Test cảnh báo": "multi_object_warning",
    }

    buttons = {btn.text(): btn for btn in page.audio_section.findChildren(QPushButton)}
    for label, event_key in labels.items():
        buttons[label].click()
        assert captured[-1] == (event_key, "hardware", "female")


def test_settings_audio_selection_emits_runtime_sync_signals(qtbot):
    page = SettingsPage(AppConfig())
    qtbot.addWidget(page)
    modes = []
    genders = []
    page.speaker_output_mode_changed.connect(modes.append)
    page.speaker_voice_gender_changed.connect(genders.append)

    page.audio_section.computer_button.click()
    page.audio_section.male_voice_button.click()

    assert modes == ["computer_speaker"]
    assert genders == ["male"]


def test_settings_hardware_test_button_emits_command(qtbot):
    cfg = AppConfig()
    cfg.uart.port = "COM8"
    page = SettingsPage(cfg)
    qtbot.addWidget(page)
    page.uart_port.clear()
    page.uart_port.addItem("COM8 (USB) Arduino", "COM8")
    page.uart_port.setCurrentIndex(0)
    captured = []
    page.test_hardware_requested.connect(lambda port, baud, cmd: captured.append((port, baud, cmd)))
    button = next(
        btn
        for btn in page.findChildren(QPushButton)
        if btn.text() == "Test Hữu cơ" and not _is_descendant(btn, page.audio_section)
    )

    button.click()

    assert captured == [("COM8", 9600, "O")]
    page.set_uart_test_result(True, "ACK:O")
    assert "ACK:O" in page.uart_test_result.text()
