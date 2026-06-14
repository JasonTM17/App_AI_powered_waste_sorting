import json
import os
import tempfile
from pathlib import Path
from typing import ClassVar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QThread, Signal

import app.ui.controller as controller_module
from app.core.config import AppConfig, ClassMapping
from app.core.dataset_queue import is_trainable_meta, save_reviewed_camera_annotation
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


class _FakeModelLoadWorker(QThread):
    done = Signal(object, str, float)
    instances: ClassVar[list] = []

    def __init__(self, *args):
        super().__init__()
        self.args = args
        self.started = False
        _FakeModelLoadWorker.instances.append(self)

    def start(self):
        self.started = True


class _FakeRuntimeLock:
    def release(self):
        pass


class _SpeakerSpy:
    def __init__(self):
        self.warning_calls = 0
        self.commands = []
        self.events = []

    def preview_warning(self):
        self.warning_calls += 1
        return True

    def preview_command(self, command):
        self.commands.append(command)
        return True

    def preview_event(self, event_key, *, voice_gender=None):
        self.events.append((event_key, voice_gender))
        return True


class _RefreshSpy:
    def __init__(self):
        self.calls = 0

    def refresh_manual_references(self):
        self.calls += 1


class _StopWorkerSpy:
    def __init__(self, running: bool = False):
        self.running = running
        self.stopped = False
        self.waited: list[int] = []
        self.deleted = False
        self.interrupted = False
        self.quit_called = False

    def stop(self):
        self.stopped = True
        self.running = False

    def wait(self, ms: int):
        self.waited.append(ms)
        self.running = False
        return True

    def isRunning(self):  # noqa: N802
        return self.running

    def deleteLater(self):  # noqa: N802
        self.deleted = True

    def requestInterruption(self):  # noqa: N802
        self.interrupted = True

    def quit(self):
        self.quit_called = True


class _LockSpy:
    def __init__(self):
        self.released = False

    def release(self):
        self.released = True


class _ClosablePipelineSpy(_PipelineSpy):
    def __init__(self):
        super().__init__()
        self.closed = False

    def close(self):
        self.closed = True


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


def test_uart_blank_port_retries_then_auto_selects_usb_port(tmp_path, monkeypatch):
    _FakeUartWorker.instances.clear()
    visible_ports: list[dict] = []
    monkeypatch.setattr(serial_enum, "list_serial_ports", lambda: list(visible_ports))
    monkeypatch.setattr(controller_module, "UartWorker", _FakeUartWorker)
    monkeypatch.setattr(controller_module, "acquire_runtime_lock", lambda _name: _FakeRuntimeLock())
    cfg = AppConfig()
    cfg.uart.port = ""
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    spy = _PipelineSpy()
    controller._pipeline = spy
    scheduled: list[bool] = []

    def _mark_retry_scheduled():
        controller._uart_retry_scheduled = True
        scheduled.append(True)

    controller._schedule_uart_retry = _mark_retry_scheduled  # type: ignore[method-assign]

    controller._start_uart_if_configured()

    assert scheduled == [True]
    assert controller._uart is None
    assert spy.uart is None

    visible_ports[:] = [
        {"device": "COM8", "name": "USB-SERIAL CH340", "hwid": "USB VID:PID=1A86:7523", "is_usb": True}
    ]
    controller._retry_start_uart()

    assert len(_FakeUartWorker.instances) == 1
    worker = _FakeUartWorker.instances[0]
    assert worker.started is True
    assert worker.port == "COM8"
    assert spy.uart is worker
    assert controller.cfg.uart.port == "COM8"
    saved = json.loads((tmp_path / "cfg.json").read_text(encoding="utf-8"))
    assert saved["uart"]["port"] == "COM8"


def test_uart_autoselect_env_guard_prevents_desktop_worker_start(tmp_path, monkeypatch):
    _FakeUartWorker.instances.clear()
    monkeypatch.setenv("TRASH_SORTER_DISABLE_UART_AUTO_SELECT", "1")
    monkeypatch.setattr(
        serial_enum,
        "list_serial_ports",
        lambda: [
            {"device": "COM8", "name": "USB-SERIAL CH340", "hwid": "USB VID:PID=1A86:7523", "is_usb": True}
        ],
    )
    monkeypatch.setattr(controller_module, "UartWorker", _FakeUartWorker)
    cfg = AppConfig()
    cfg.uart.port = ""
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    spy = _PipelineSpy()
    controller._pipeline = spy
    scheduled: list[bool] = []
    controller._schedule_uart_retry = lambda: scheduled.append(True)  # type: ignore[method-assign]

    controller._start_uart_if_configured()

    assert _FakeUartWorker.instances == []
    assert scheduled == []
    assert spy.uart is None
    assert controller.cfg.uart.port == ""


def test_controller_start_schedules_model_load_without_blocking(tmp_path, monkeypatch):
    _FakeModelLoadWorker.instances.clear()
    monkeypatch.setattr(serial_enum, "list_serial_ports", lambda: [])
    monkeypatch.setattr(controller_module, "_ModelLoadWorker", _FakeModelLoadWorker)
    cfg = AppConfig()
    cfg.uart.auto_reconnect = False
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    model_states: list[bool] = []
    controller.model_status.connect(model_states.append)

    controller.start()

    assert len(_FakeModelLoadWorker.instances) == 1
    assert _FakeModelLoadWorker.instances[0].started is True
    assert controller._model_loading is True
    assert controller._pipeline is None
    assert model_states == [False]
    controller.stop()


def test_controller_stop_releases_workers_and_runtime_buffers(tmp_path):
    cfg = AppConfig()
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    inference = _StopWorkerSpy()
    model_loader = _StopWorkerSpy()
    probe = _StopWorkerSpy()
    lock = _LockSpy()
    pipeline = _ClosablePipelineSpy()
    controller._inference_worker = inference  # type: ignore[assignment]
    controller._model_loader = model_loader  # type: ignore[assignment]
    controller._model_loading = True
    controller._camera_lock = lock  # type: ignore[assignment]
    controller._pipeline = pipeline  # type: ignore[assignment]
    controller._last_frame = np.zeros((8, 8, 3), dtype=np.uint8)
    controller._annotation_frame = np.zeros((8, 8, 3), dtype=np.uint8)
    controller._last_detections = [{"cls_name": "Textile"}]
    controller._pending_camera_start = True
    controller._pending_uart_tests[-1] = ("R", "SORT:R", "COM8", 0.0)
    controller._probes.append(probe)  # type: ignore[arg-type]

    controller.stop()

    assert lock.released is True
    assert inference.stopped is True
    assert inference.deleted is True
    assert model_loader.deleted is True
    assert probe.interrupted is True
    assert probe.quit_called is True
    assert controller._probes == []
    assert pipeline.closed is True
    assert controller._pipeline is None
    assert controller._last_frame is None
    assert controller._annotation_frame is None
    assert controller._last_detections == []
    assert controller._pending_camera_start is False
    assert controller._pending_uart_tests == {}


def test_start_camera_defers_until_model_ready(tmp_path):
    cfg = AppConfig()
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    errors: list[str] = []
    controller.camera_error.connect(errors.append)

    controller.start_camera()

    assert controller._pending_camera_start is True
    assert errors and "Model" in errors[0]
    controller.stop()


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
    cfg.roi.enabled = True
    cfg.roi.width = 640
    cfg.roi.height = 480
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    spy = _PipelineSpy()
    controller._pipeline = spy
    controller.is_camera_running = lambda: True  # type: ignore[method-assign]
    controller.is_uart_connected = lambda: True  # type: ignore[method-assign]

    controller.set_actuation_test_mode(True)

    assert controller.is_actuation_test_mode_enabled() is True
    assert spy.dispatch_enabled is True
    assert spy.reset_count == 1

    controller.set_actuation_test_mode(False)

    assert controller.is_actuation_test_mode_enabled() is False
    assert spy.dispatch_enabled is False
    assert spy.reset_count == 2


def test_laptop_voice_warning_previews_warning_audio(tmp_path):
    cfg = AppConfig()
    cfg.speaker.output_mode = "computer_speaker"
    cfg.speaker.enabled = True
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    speaker = _SpeakerSpy()
    controller._speaker = speaker
    results = []
    controller.test_uart_result.connect(lambda ok, msg: results.append((ok, msg)))

    try:
        controller.test_laptop_voice("warning")
    finally:
        controller.stop()

    assert speaker.warning_calls == 0
    assert speaker.events == [("multi_object_warning", "female")]
    assert speaker.commands == []
    assert results and results[0][0] is True


def test_hardware_audio_event_uses_audio_only_uart_command(tmp_path):
    class _AudioUart:
        is_connected = True

        def __init__(self):
            self.sent = []

        def isRunning(self):  # noqa: N802
            return True

        def send_audio_test(self, track_id, track):
            self.sent.append((track_id, track))

    cfg = AppConfig()
    cfg.uart.port = "COM8"
    cfg.speaker.output_mode = "hardware"
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    uart = _AudioUart()
    controller._uart = uart  # type: ignore[assignment]

    controller.test_audio_event("sort_R", "hardware", "female")

    assert uart.sent == [(-2, 4)]
    assert controller._pending_uart_tests[-2][:3] == ("AUDIO:4", "AUDIO:4\n", "COM8")


def test_auto_sort_rejects_enable_until_camera_uart_and_roi_are_ready(tmp_path):
    cfg = AppConfig()
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    spy = _PipelineSpy()
    controller._pipeline = spy
    results = []
    controller.test_uart_result.connect(lambda ok, msg: results.append((ok, msg)))

    controller.set_actuation_test_mode(True)

    assert controller.is_actuation_test_mode_enabled() is False
    assert spy.dispatch_enabled is False
    assert results and results[-1][0] is False


def test_auto_sort_rejects_roi_outside_configured_camera_frame(tmp_path):
    cfg = AppConfig()
    cfg.camera.width = 640
    cfg.camera.height = 480
    cfg.roi.enabled = True
    cfg.roi.x = 260
    cfg.roi.y = 80
    cfg.roi.width = 820
    cfg.roi.height = 360
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    spy = _PipelineSpy()
    controller._pipeline = spy
    controller.is_camera_running = lambda: True  # type: ignore[method-assign]
    controller.is_uart_connected = lambda: True  # type: ignore[method-assign]
    results = []
    controller.test_uart_result.connect(lambda ok, msg: results.append((ok, msg)))

    controller.set_actuation_test_mode(True)

    assert controller.is_actuation_test_mode_enabled() is False
    assert spy.dispatch_enabled is False
    assert results and results[-1][0] is False
    assert "ROI" in results[-1][1]


def test_capture_reviewed_camera_sample_writes_trainable_item(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = AppConfig()
    cfg.capture.output_dir = str(tmp_path / "dataset")
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    controller._last_frame = np.zeros((80, 120, 3), dtype=np.uint8)
    controller.is_camera_running = lambda: True  # type: ignore[method-assign]
    refresh = _RefreshSpy()
    controller._pipeline = refresh  # type: ignore[assignment]
    saved: list[str] = []
    controller.capture_saved.connect(saved.append)

    controller.capture_reviewed_camera_sample("miếng vải", 0, (10, 12, 100, 70), True)

    assert saved
    image_path = Path(saved[0])
    meta = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["boxes"][0]["cls_name"] == "Textile"
    assert meta["boxes"][0]["cls_id"] == 37
    assert meta["reviewed"] is True
    assert meta["bbox_reviewed"] is True
    assert is_trainable_meta(meta) is True
    assert refresh.calls == 1


def test_import_manual_phone_samples_writes_pending_review_item(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    src = tmp_path / "phone.jpg"
    import cv2

    cv2.imwrite(str(src), np.full((48, 64, 3), 180, dtype=np.uint8))
    cfg = AppConfig()
    cfg.capture.output_dir = str(tmp_path / "dataset")
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    saved: list[str] = []
    messages: list[tuple[bool, str]] = []
    controller.capture_saved.connect(saved.append)
    controller.snapshot_saved.connect(lambda ok, msg: messages.append((ok, msg)))

    controller.import_manual_phone_samples("vải", 37, [str(src)])

    queue_dir = Path(cfg.capture.output_dir) / "low_conf_queue"
    images = list(queue_dir.glob("manual_phone_*.jpg"))
    assert len(images) == 1
    meta = json.loads(images[0].with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["source"] == "manual_phone_import"
    assert meta["boxes"][0]["cls_name"] == "Textile"
    assert meta["boxes"][0]["cls_id"] == 37
    assert meta["reviewed"] is False
    assert meta["bbox_reviewed"] is False
    assert meta["needs_annotation"] is True
    assert meta["recognition_enabled"] is False
    assert is_trainable_meta(meta) is False
    assert saved
    assert messages and messages[-1][0] is True


def test_start_learn_now_candidate_training_uses_reviewed_textile_samples(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = AppConfig()
    cfg.capture.output_dir = str(tmp_path / "dataset")
    queue_dir = Path(cfg.capture.output_dir) / "low_conf_queue"
    frame = np.zeros((80, 120, 3), dtype=np.uint8)
    for index in range(6):
        save_reviewed_camera_annotation(
            frame,
            queue_dir,
            "Textile",
            37,
            (10, 12, 100, 70),
            catalog_path=tmp_path / "dataset.db",
            extra_meta={"sample_index": index},
        )

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(controller_module, "training_processes", lambda: [])
    monkeypatch.setattr(
        controller_module,
        "start_learn_now_training",
        lambda _root, cls_name, profile: calls.append((cls_name, profile)) or 4321,
    )
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    results: list[tuple[bool, str]] = []
    statuses: list[object] = []
    controller.learn_now_action_result.connect(lambda ok, msg: results.append((ok, msg)))
    controller.training_status_changed.connect(statuses.append)

    controller.start_learn_now_candidate_training("miếng vải", "micro")

    assert calls == [("Textile", "micro")]
    assert results and results[0][0] is True
    assert statuses
    controller.stop()


def test_start_learn_now_candidate_training_blocks_when_actuation_enabled(tmp_path, monkeypatch):
    cfg = AppConfig()
    cfg.capture.output_dir = str(tmp_path / "dataset")
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    controller._actuation_test_enabled = True
    results: list[tuple[bool, str]] = []
    controller.learn_now_action_result.connect(lambda ok, msg: results.append((ok, msg)))
    monkeypatch.setattr(
        controller_module,
        "start_learn_now_training",
        lambda *_args, **_kwargs: pytest.fail("training must stay blocked"),
    )

    controller.start_learn_now_candidate_training("Textile", "micro")

    assert results
    assert results[0][0] is False
    assert "Arduino" in results[0][1]


def test_learn_now_status_worker_discards_stale_class_result(tmp_path, monkeypatch, qtbot):
    import time

    cfg = AppConfig()
    cfg.capture.output_dir = str(tmp_path / "dataset")
    controller = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    calls: list[str] = []
    statuses: list[object] = []

    def fake_status(_queue_dir, class_name, _catalog_path):
        calls.append(class_name)
        time.sleep(0.08 if class_name == "Pen" else 0.01)
        return {"selected": {"class_name": class_name}}

    monkeypatch.setattr(controller_module, "build_selected_learn_now_status", fake_status)
    controller.learn_now_status_changed.connect(statuses.append)

    controller.refresh_learn_now_status("Pen")
    controller.refresh_learn_now_status("Textile")
    qtbot.waitUntil(lambda: bool(statuses), timeout=2000)
    controller.stop()

    assert calls == ["Pen", "Textile"]
    assert statuses == [{"selected": {"class_name": "Textile"}}]
