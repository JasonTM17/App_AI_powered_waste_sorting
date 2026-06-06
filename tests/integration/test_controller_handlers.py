import os
import tempfile
from pathlib import Path
from typing import ClassVar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QThread, Signal

import app.ui.controller as controller_module
from app.core.config import AppConfig, ClassMapping
from app.ui.controller import AppController
from app.utils import serial_enum


@pytest.fixture
def ctl(qtbot):
    cfg = AppConfig(mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)])
    with tempfile.TemporaryDirectory() as td:
        c = AppController(cfg, Path(td) / "cfg.json", Path(td) / "h.db")
        yield c


def _wait(cond, timeout=2.0):
    import time

    deadline = time.time() + timeout
    while not cond() and time.time() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.02)


def test_test_camera_emits_failure_for_bad_source(ctl):
    results = []
    ctl.test_camera_result.connect(lambda ok, msg: results.append((ok, msg)))
    ctl.test_camera("nonexistent_dev_99")
    _wait(lambda: bool(results), 3.0)
    assert results
    assert results[0][0] is False


def test_test_uart_emits_failure_for_bad_port(ctl):
    results = []
    ctl.test_uart_result.connect(lambda ok, msg: results.append((ok, msg)))
    ctl.test_uart_ping("COM_NOT_REAL", 9600)
    _wait(lambda: bool(results), 3.0)
    assert results
    assert results[0][0] is False


def test_reload_model_emits_failure_for_bad_path(ctl):
    results = []
    ctl.reload_model_result.connect(lambda ok, msg: results.append((ok, msg)))
    ctl.reload_model("does_not_exist.pt")
    _wait(lambda: bool(results), 3.0)
    assert results
    assert results[0][0] is False


class _PipelineSpy:
    def __init__(self):
        self.uart = "initial"
        self.cfg = None
        self.dispatch_enabled = None
        self.reset_count = 0

    def set_uart(self, uart):
        self.uart = uart

    def update_mappings(self, _mappings):
        pass

    def on_ack(self, *_args):
        pass

    def set_hardware_dispatch_enabled(self, enabled):
        self.dispatch_enabled = enabled

    def reset_dispatch_state(self):
        self.reset_count += 1


class _FakeUartWorker(QThread):
    ack_received = Signal(int, str, str, object)
    connected = Signal(bool)
    instances: ClassVar[list] = []

    def __init__(
        self,
        port="",
        baud=9600,
        ack_timeout_ms=200,
        auto_reconnect=True,
        protocol="sort_line",
    ):
        super().__init__()
        self.port = port
        self.baud = baud
        self.ack_timeout_ms = ack_timeout_ms
        self.auto_reconnect = auto_reconnect
        self.protocol = protocol
        self.started = False
        self.stopped = False
        _FakeUartWorker.instances.append(self)

    def start(self):
        self.started = True

    def isRunning(self):  # noqa: N802
        return self.started and not self.stopped

    def stop(self):
        self.stopped = True


class _FakeRuntimeLock:
    def release(self):
        pass


def test_uart_preserves_configured_port_when_temporarily_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(serial_enum, "list_serial_ports", lambda: [])
    cfg = AppConfig()
    cfg.uart.port = "COM9"
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    spy = _PipelineSpy()
    controller._pipeline = spy

    controller._start_uart_if_configured()

    assert controller._uart is None
    assert spy.uart is None
    assert controller.cfg.uart.port == "COM9"


def test_uart_clears_present_non_usb_port(tmp_path, monkeypatch):
    monkeypatch.setattr(
        serial_enum,
        "list_serial_ports",
        lambda: [{"device": "COM3", "name": "Bluetooth", "hwid": "BTHENUM", "is_usb": False}],
    )
    cfg = AppConfig()
    cfg.uart.port = "COM3"
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    spy = _PipelineSpy()
    controller._pipeline = spy

    controller._start_uart_if_configured()

    assert controller._uart is None
    assert spy.uart is None
    assert controller.cfg.uart.port == ""


def test_update_config_starts_usb_uart_and_updates_pipeline(tmp_path, monkeypatch):
    _FakeUartWorker.instances.clear()
    monkeypatch.setattr(
        serial_enum,
        "list_serial_ports",
        lambda: [{"device": "COM7", "name": "Arduino", "hwid": "USB VID:PID", "is_usb": True}],
    )
    monkeypatch.setattr(controller_module, "UartWorker", _FakeUartWorker)
    monkeypatch.setattr(controller_module, "acquire_runtime_lock", lambda _name: _FakeRuntimeLock())
    cfg = AppConfig()
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    spy = _PipelineSpy()
    controller._pipeline = spy
    new_cfg = cfg.model_copy(deep=True)
    new_cfg.uart.port = "COM7"
    new_cfg.uart.baud = 115200

    controller.update_config(new_cfg)

    assert len(_FakeUartWorker.instances) == 1
    worker = _FakeUartWorker.instances[0]
    assert worker.started is True
    assert worker.port == "COM7"
    assert worker.baud == 115200
    assert worker.protocol == "plain_group"
    assert spy.uart is worker


def test_actuation_test_mode_controls_pipeline_dispatch(tmp_path):
    cfg = AppConfig()
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    spy = _PipelineSpy()
    controller._pipeline = spy

    controller.set_actuation_test_mode(True)

    assert controller.is_actuation_test_mode_enabled() is True
    assert spy.dispatch_enabled is True
    assert spy.reset_count == 1

    controller.set_actuation_test_mode(False)

    assert controller.is_actuation_test_mode_enabled() is False
    assert spy.dispatch_enabled is False
    assert spy.reset_count == 2
