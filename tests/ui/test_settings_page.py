import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QPushButton

from app.core.config import AppConfig
from app.ui.pages.settings import SettingsPage


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
    button = next(btn for btn in page.findChildren(QPushButton) if btn.text() == "Test Huu co")

    button.click()

    assert captured == [("COM8", 9600, "O")]
    page.set_uart_test_result(True, "ACK:O")
    assert "ACK:O" in page.uart_test_result.text()
