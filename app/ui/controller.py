"""Glue between core workers and UI signals/slots."""

from __future__ import annotations

import os
import time
from contextlib import suppress
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QThread, QTimer, Signal

from app.core.camera import CameraWorker, SharedCameraWorker
from app.core.config import (
    AppConfig,
    computer_speaker_enabled,
    normalize_speaker_output_config,
    save_config,
)
from app.core.hardware_profile import route_for_command
from app.core.inference import InferenceEngine
from app.core.inference_worker import InferenceWorker
from app.core.learn_now import build_selected_learn_now_status
from app.core.learn_now_training import (
    build_training_status,
    start_learn_now_training,
    stop_training_processes,
    training_processes,
)
from app.core.pipeline import Pipeline
from app.core.speaker import WasteSpeaker
from app.core.uart import UartWorker
from app.core.uart_protocol import UartProtocol, encode_sort
from app.core.voice_pack import (
    AUDIO_EVENT_LABELS,
    AUDIO_EVENT_TRACKS,
    normalize_voice_gender,
)
from app.core.waste_categories import canonical_class_name
from app.utils import serial_enum
from app.utils.camera_frame_quality import evaluate_frame_quality
from app.utils.camera_source import backend_hint, normalize_camera_source
from app.utils.logging import logger
from app.utils.paths import dataset_db_path
from app.utils.runtime_lock import RuntimeLock, RuntimeLockError, acquire_runtime_lock
from app.utils.shared_camera_stream import SharedFramePublisher


class _CamProbe(QThread):
    done = Signal(bool, str)

    def __init__(self, source: str):
        super().__init__()
        self._src = source

    def run(self):
        import cv2

        try:
            src_raw = normalize_camera_source(self._src)
            src = int(src_raw) if src_raw.isdigit() else src_raw
            attempts = [("ANY", cv2.CAP_ANY)]
            if isinstance(src, int):
                attempts = [
                    ("DSHOW", cv2.CAP_DSHOW),
                    ("MSMF", cv2.CAP_MSMF),
                    ("ANY", cv2.CAP_ANY),
                ]
                hint = backend_hint(self._src)
                if hint:
                    attempts = [item for item in attempts if item[0] == hint]
            last_error = "Cannot open source"
            for name, api in attempts:
                cap = cv2.VideoCapture(src, api) if isinstance(src, int) else cv2.VideoCapture(src)
                ok = cap.isOpened()
                if ok:
                    ok, frame = cap.read()
                    quality = evaluate_frame_quality(frame if ok else None)
                    ok = ok and quality.usable
                else:
                    quality = None
                cap.release()
                if ok:
                    self.done.emit(True, f"OK ({name})")
                    return
                reason = quality.reason if quality is not None else "cannot open source"
                last_error = f"Cannot use source ({name}): {reason}"
            self.done.emit(False, last_error)
        except Exception as e:
            self.done.emit(False, str(e))


class _UartProbe(QThread):
    done = Signal(bool, str)

    def __init__(
        self,
        port: str,
        baud: int,
        protocol: UartProtocol = "plain_group",
        command: str | None = None,
    ):
        super().__init__()
        self._port = port
        self._baud = baud
        self._protocol = protocol
        self._command = command

    def run(self):
        import time as _t

        import serial

        from app.core.uart_protocol import (
            encode_ping,
            encode_sort,
            expected_ack_command,
            parse_line,
        )

        try:
            s = serial.Serial(self._port, self._baud, timeout=1.0)
        except Exception as e:
            self.done.emit(False, f"open {self._port} failed: {e}")
            return
        try:
            if self._command:
                command = self._command.strip().upper()
                payload = encode_sort(command, 0.99, protocol=self._protocol)
                expected_ack = expected_ack_command(command, self._protocol)
                s.write(payload)
                deadline = _t.time() + 4.5
                while _t.time() < deadline:
                    raw = s.readline()
                    if not raw:
                        continue
                    msg = parse_line(raw)
                    if msg and msg[0] == "ack" and msg[1] == expected_ack:
                        elapsed = int((4.5 - max(0.0, deadline - _t.time())) * 1000)
                        self.done.emit(
                            True,
                            f"sent {payload.decode('utf-8').strip()} on {self._port}; ACK:{expected_ack}; {elapsed} ms",
                        )
                        return
                    if msg and msg[0] == "nack" and msg[1] == expected_ack:
                        self.done.emit(False, f"NACK:{expected_ack}:{msg[2] or ''}")
                        return
                self.done.emit(False, f"sent {payload.decode('utf-8').strip()} on {self._port}; no ACK")
                return
            s.write(encode_ping())
            deadline = _t.time() + 1.5
            while _t.time() < deadline:
                raw = s.readline()
                if not raw:
                    continue
                msg = parse_line(raw)
                if msg and msg[0] == "pong":
                    self.done.emit(True, f"PONG from {self._port}")
                    return
            self.done.emit(False, f"no PONG from {self._port} within 1.5s")
        finally:
            with suppress(Exception):
                s.close()


class _ModelLoadWorker(QThread):
    done = Signal(object, str, float)

    def __init__(
        self,
        model_path: str,
        device: str,
        conf: float,
        iou: float,
        imgsz: int,
        half: bool,
        specialist,
    ):
        super().__init__()
        self._model_path = model_path
        self._device = device
        self._conf = conf
        self._iou = iou
        self._imgsz = imgsz
        self._half = half
        self._specialist = specialist

    def run(self):
        started = time.perf_counter()
        try:
            engine = InferenceEngine(
                self._model_path,
                device=self._device,
                conf=self._conf,
                iou=self._iou,
                imgsz=self._imgsz,
                half=self._half,
                specialist=self._specialist,
            )
        except Exception as exc:
            self.done.emit(None, str(exc), time.perf_counter() - started)
            return
        self.done.emit(engine, "", time.perf_counter() - started)


class _LearnNowStatusWorker(QThread):
    done = Signal(int, object, str, float)

    def __init__(
        self,
        request_id: int,
        queue_dir: Path,
        class_name: str,
        catalog_path: Path,
    ) -> None:
        super().__init__()
        self._request_id = request_id
        self._queue_dir = queue_dir
        self._class_name = class_name
        self._catalog_path = catalog_path

    def run(self) -> None:
        started = time.perf_counter()
        try:
            status = build_selected_learn_now_status(
                self._queue_dir,
                self._class_name,
                self._catalog_path,
            )
        except Exception as exc:
            self.done.emit(self._request_id, {}, str(exc), time.perf_counter() - started)
            return
        self.done.emit(self._request_id, status, "", time.perf_counter() - started)


class _TrainingStatusWorker(QThread):
    done = Signal(object, str, float)

    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self._project_root = project_root

    def run(self) -> None:
        started = time.perf_counter()
        try:
            status = build_training_status(self._project_root)
        except Exception as exc:
            self.done.emit({}, str(exc), time.perf_counter() - started)
            return
        self.done.emit(status, "", time.perf_counter() - started)


class AppController(QObject):
    camera_status = Signal(bool)
    uart_status = Signal(bool, str)
    model_status = Signal(bool)
    frame_processed = Signal(object, list, float, float)
    test_camera_result = Signal(bool, str)
    test_uart_result = Signal(bool, str)
    reload_model_result = Signal(bool, str)
    snapshot_saved = Signal(bool, str)
    capture_saved = Signal(str)
    camera_error = Signal(str)
    learn_now_status_changed = Signal(object)
    learn_now_action_result = Signal(bool, str)
    training_status_changed = Signal(object)
    actuation_mode_changed = Signal(bool)

    def __init__(self, cfg: AppConfig, config_path: Path, db_path: Path):
        super().__init__()
        self.cfg = cfg
        self.config_path = config_path
        self.db_path = db_path
        self._engine: InferenceEngine | None = None
        self._camera: CameraWorker | SharedCameraWorker | None = None
        self._camera_lock: RuntimeLock | None = None
        self._camera_shared_mode = False
        self._shared_publisher = SharedFramePublisher()
        self._uart: UartWorker | None = None
        self._uart_lock: RuntimeLock | None = None
        self._pipeline: Pipeline | None = None
        self._speaker = WasteSpeaker(
            enabled=computer_speaker_enabled(self.cfg),
            cooldown_seconds=self.cfg.speaker.cooldown_seconds,
            voice_gender=self.cfg.speaker.voice_gender,
        )
        self._inference_worker: InferenceWorker | None = None
        self._last_frame_t = 0.0
        self._fps = 0.0
        self._latency = 0.0
        self._last_frame = None
        self._last_detections = []
        self._annotation_frame = None
        self._probes: list[QThread] = []
        self._pending_uart_tests: dict[int, tuple[str, str, str, float]] = {}
        # -1 is reserved by UartWorker for automatic warning audio.
        self._next_uart_test_id = -2
        self._actuation_test_enabled = False
        self._uart_retry_scheduled = False
        self._model_loader: _ModelLoadWorker | None = None
        self._model_loading = False
        self._pending_camera_start = False
        self._last_uart_retry_log_key = ""
        self._uart_retry_log_count = 0
        self._learn_now_worker: _LearnNowStatusWorker | None = None
        self._learn_now_request_id = 0
        self._pending_learn_now_class: str | None = None
        self._training_status_worker: _TrainingStatusWorker | None = None
        self._training_status_pending = False

    def _track_probe(self, worker: QThread) -> None:
        worker.finished.connect(lambda worker=worker: self._forget_probe(worker))
        worker.finished.connect(worker.deleteLater)
        self._probes.append(worker)
        worker.start()

    def _forget_probe(self, worker: QThread) -> None:
        with suppress(ValueError):
            self._probes.remove(worker)

    def _clear_runtime_buffers(self) -> None:
        self._last_frame = None
        self._last_detections = []
        self._annotation_frame = None
        self._last_frame_t = 0.0
        self._fps = 0.0
        self._latency = 0.0

    def start(self) -> None:
        self._start_uart_if_configured()
        self._start_model_loader()

        # Camera is no longer auto-started. User opts in from Live page.
        # This avoids holding the camera handle while idle and lets the
        # user tweak Settings before the device is opened.
        self.camera_status.emit(False)
        self.model_status.emit(False)
        logger.info("controller started (model loading in background; camera idle)")

    def _start_model_loader(self) -> None:
        if self._model_loading or self._engine is not None:
            return
        self._model_loading = True
        worker = _ModelLoadWorker(
            self.cfg.model.path,
            self.cfg.model.device,
            self.cfg.model.conf_threshold,
            self.cfg.model.iou_threshold,
            self.cfg.model.input_size,
            self.cfg.model.half_precision,
            self.cfg.model.specialist,
        )
        worker.done.connect(self._on_model_loaded)
        worker.finished.connect(worker.deleteLater)
        self._model_loader = worker
        worker.start()
        logger.info("model load scheduled in background path={}", self.cfg.model.path)

    def _on_model_loaded(self, engine: object, error: str, elapsed_s: float) -> None:
        self._model_loading = False
        self._model_loader = None
        if error or engine is None:
            logger.warning("model background load failed after {:.0f} ms: {}", elapsed_s * 1000, error)
            self.model_status.emit(False)
            self.reload_model_result.emit(False, f"Không tải được model: {error}")
            return
        self._engine = engine
        self._pipeline = Pipeline(
            self.cfg,
            self._engine,
            self._uart,
            self.db_path,
            speaker=self._speaker,
        )
        self._configure_camera_dispatch()
        self._pipeline.on_capture_saved = self.capture_saved.emit
        self._inference_worker = InferenceWorker(self._pipeline)
        self._inference_worker.processed.connect(self._on_inferred)
        self._inference_worker.start()
        self.model_status.emit(True)
        logger.info("model ready in background elapsed_ms={:.0f}", elapsed_s * 1000)
        if self._pending_camera_start:
            self._pending_camera_start = False
            QTimer.singleShot(0, self.start_camera)

    def _is_usb_uart_port(self, port: str) -> bool:
        if not port:
            return False
        ports = serial_enum.list_serial_ports()
        wanted = port.strip().upper()
        return any(
            str(p.get("device", "")).strip().upper() == wanted
            and serial_enum.is_eligible_usb_serial_port(p)
            for p in ports
        )

    def _uart_port_presence(self, port: str) -> tuple[bool, bool]:
        wanted = port.strip().upper()
        if not wanted:
            return False, False
        for candidate in serial_enum.list_serial_ports():
            if str(candidate.get("device", "")).strip().upper() != wanted:
                continue
            return True, serial_enum.is_eligible_usb_serial_port(candidate)
        return False, False

    def _auto_select_uart_if_blank(self) -> None:
        if self.cfg.uart.port.strip():
            return
        if os.environ.get("TRASH_SORTER_DISABLE_UART_AUTO_SELECT") == "1":
            logger.info("uart auto-select disabled by environment")
            return
        result = serial_enum.select_single_usb_serial_port(serial_enum.list_serial_ports())
        if not result.selected:
            logger.info("uart auto-select skipped: {}", result.message)
            return
        self.cfg.uart.port = result.port
        save_config(self.cfg, self.config_path)
        logger.info("uart auto-selected port={}", result.port)

    def _sanitize_uart_config(self, cfg: AppConfig) -> AppConfig:
        clean = cfg.model_copy(deep=True)
        port = clean.uart.port.strip()
        clean.uart.port = port if self._is_usb_uart_port(port) else ""
        return clean

    def _start_uart_if_configured(self) -> None:
        if self._uart is not None and self._uart.isRunning():
            return
        self._auto_select_uart_if_blank()
        port = self.cfg.uart.port.strip()
        if not port and os.environ.get("TRASH_SORTER_DISABLE_UART_AUTO_SELECT") == "1":
            if self._pipeline is not None:
                self._pipeline.set_uart(None)
            self.uart_status.emit(False, "")
            return
        if not self._is_usb_uart_port(port):
            if port:
                present, eligible = self._uart_port_presence(port)
                if present and not eligible:
                    logger.info("uart port ignored because it is not USB/Arduino: {}", port)
                    self.cfg.uart.port = ""
                    save_config(self.cfg, self.config_path)
                else:
                    self._log_uart_retry(
                        f"waiting:{port}",
                        f"uart port {port} not visible yet; keeping config and retrying",
                    )
                    self._schedule_uart_retry()
            else:
                self._log_uart_retry("blank", "uart port blank; waiting for USB/Arduino and retrying")
                self._schedule_uart_retry()
            if self._pipeline is not None:
                self._pipeline.set_uart(None)
            self.uart_status.emit(False, "")
            return

        try:
            self._uart_lock = acquire_runtime_lock("uart")
        except RuntimeLockError as e:
            logger.warning("uart start refused: {}", e)
            if self._pipeline is not None:
                self._pipeline.set_uart(None)
            self.uart_status.emit(False, "")
            self._schedule_uart_retry()
            return
        worker = UartWorker(
            port=port,
            baud=self.cfg.uart.baud,
            ack_timeout_ms=self.cfg.uart.ack_timeout_ms,
            auto_reconnect=self.cfg.uart.auto_reconnect,
            protocol=self.cfg.uart.protocol,
        )
        worker.connected.connect(self._on_uart_connected)
        worker.ack_received.connect(self._on_uart_ack)
        if self._pipeline is not None:
            self._pipeline.set_uart(worker)
        self._uart = worker
        self._uart_retry_scheduled = False
        self._last_uart_retry_log_key = ""
        self._uart_retry_log_count = 0
        self._uart.start()
        logger.info("uart start requested port={}", port)

    def _log_uart_retry(self, key: str, message: str) -> None:
        if key != self._last_uart_retry_log_key:
            self._last_uart_retry_log_key = key
            self._uart_retry_log_count = 0
        self._uart_retry_log_count += 1
        if self._uart_retry_log_count == 1:
            logger.info(message)
            return
        if self._uart_retry_log_count % 15 == 0:
            logger.info("{} (retry {})", message, self._uart_retry_log_count)

    def _schedule_uart_retry(self) -> None:
        if self._uart_retry_scheduled or not self.cfg.uart.auto_reconnect:
            return
        self._uart_retry_scheduled = True
        QTimer.singleShot(2000, self._retry_start_uart)

    def _retry_start_uart(self) -> None:
        self._uart_retry_scheduled = False
        if self._uart is not None and self._uart.isRunning():
            return
        self._start_uart_if_configured()

    def _stop_uart_worker(self) -> None:
        if self._uart is None:
            self._uart_retry_scheduled = False
            if self._pipeline is not None:
                self._pipeline.set_uart(None)
            if self._uart_lock is not None:
                self._uart_lock.release()
                self._uart_lock = None
            self.uart_status.emit(False, "")
            return
        worker = self._uart
        self._uart = None
        self._uart_retry_scheduled = False
        with suppress(RuntimeError, TypeError):
            worker.connected.disconnect(self._on_uart_connected)
        with suppress(RuntimeError, TypeError):
            worker.ack_received.disconnect(self._on_uart_ack)
        if self._pipeline is not None:
            self._pipeline.set_uart(None)
        worker.stop()
        worker.wait(2000)
        worker.deleteLater()
        if self._uart_lock is not None:
            self._uart_lock.release()
            self._uart_lock = None
        self.uart_status.emit(False, "")
        logger.info("uart stopped")

    def _restart_uart_if_needed(self) -> None:
        self._stop_uart_worker()
        self._start_uart_if_configured()

    def _configure_camera_dispatch(self) -> None:
        if self._pipeline is None:
            return
        self._pipeline.set_hardware_dispatch_enabled(self._actuation_test_enabled)

    def _on_uart_connected(self, ok: bool) -> None:
        if not ok and self._actuation_test_enabled:
            self._set_auto_sort_enabled(False)
            self.test_uart_result.emit(
                False,
                "Phân loại tự động đã tắt vì UART mất kết nối.",
            )
        self.uart_status.emit(ok, self.cfg.uart.protocol)

    def _on_uart_ack(self, track_id: int, command: str, status: str, rtt_ms) -> None:
        if track_id < 0:
            pending = self._pending_uart_tests.pop(track_id, None)
            payload = pending[1] if pending else command
            port = pending[2] if pending else self.cfg.uart.port
            ok = status == "ok"
            self.test_uart_result.emit(
                ok,
                f"sent {payload.strip()} on {port}; ACK {status}; {int(rtt_ms or 0)} ms",
            )
            return
        if self._pipeline is not None:
            self._pipeline.on_ack(track_id, command, status, rtt_ms)

    def start_camera(self) -> None:
        if self._camera is not None and self._camera.isRunning():
            return
        if self._pipeline is None or self._inference_worker is None:
            self._pending_camera_start = True
            msg = "Model đang tải, camera sẽ tự bật khi model sẵn sàng."
            self.camera_error.emit(msg)
            logger.info("camera start deferred: model still loading")
            return
        from app.utils.camera_enum import find_readable_usb_camera

        usb_source = find_readable_usb_camera()
        if not usb_source:
            msg = (
                "Chưa mở được camera USB. "
                "Vui lòng cắm camera USB, đóng app khác đang dùng camera, rồi thử lại."
            )
            logger.info("camera USB unavailable, using shared stream if available: {}", msg)
            self._start_shared_camera()
            return
        try:
            self._camera_lock = acquire_runtime_lock("camera")
        except RuntimeLockError as e:
            msg = f"Camera USB đang được runtime khác sử dụng: {e}"
            logger.info("camera lock held by another runtime, using shared stream: {}", msg)
            self._start_shared_camera()
            return
        if self.cfg.camera.source != usb_source:
            logger.info("auto-selected USB camera source={}", usb_source)
            self.cfg.camera.source = usb_source
            save_config(self.cfg, self.config_path)
        self._camera = CameraWorker(
            source=self.cfg.camera.source,
            width=self.cfg.camera.width,
            height=self.cfg.camera.height,
            mirror=self.cfg.camera.mirror,
            rotation=self.cfg.camera.rotation,
        )
        self._camera.connected.connect(self.camera_status.emit)
        self._camera.frame_ready.connect(self._on_frame)
        self._camera.start()
        logger.info("camera start requested source={}", self.cfg.camera.source)

    def _start_shared_camera(self) -> None:
        self._camera_shared_mode = True
        self._camera = SharedCameraWorker()
        self._camera.connected.connect(self.camera_status.emit)
        self._camera.frame_ready.connect(self._on_frame)
        self._camera.start()
        self.camera_error.emit("Camera đang chạy qua shared stream từ runtime khác.")
        logger.info("shared camera start requested")

    def stop_camera(self) -> None:
        if self._actuation_test_enabled:
            self._set_auto_sort_enabled(False)
            self.test_uart_result.emit(
                True,
                "Đã tắt phân loại tự động vì camera dừng.",
            )
        if self._camera is None:
            if self._camera_lock is not None:
                self._camera_lock.release()
                self._camera_lock = None
            self._camera_shared_mode = False
            self.camera_status.emit(False)
            return
        cam = self._camera
        self._camera = None
        self._camera_shared_mode = False
        with suppress(RuntimeError, TypeError):
            cam.frame_ready.disconnect(self._on_frame)
        cam.stop()
        cam.wait(2000)
        cam.deleteLater()
        if self._camera_lock is not None:
            self._camera_lock.release()
            self._camera_lock = None
        self.camera_status.emit(False)
        logger.info("camera stopped")

    def is_camera_running(self) -> bool:
        return self._camera is not None and self._camera.isRunning()

    def _on_frame(self, frame: np.ndarray) -> None:
        if self._inference_worker is None:
            return
        self._last_frame = frame
        if not self._camera_shared_mode:
            self._shared_publisher.publish(frame)
        self._inference_worker.submit(frame)

    def _on_inferred(self, frame, detections, latency_ms: float) -> None:
        import time
        now = time.time()
        self._last_detections = list(detections)
        # Cap UI emit rate to ~30 fps regardless of how fast inference runs.
        # The pipeline still ran (history + UART), we just skip pushing the
        # frame to the renderer when the previous emit was very recent.
        min_interval = 1.0 / 30.0
        if self._last_frame_t and (now - self._last_frame_t) < min_interval:
            return
        self._latency = latency_ms
        if self._last_frame_t:
            inst_fps = 1.0 / max(now - self._last_frame_t, 1e-6)
            self._fps = 0.9 * self._fps + 0.1 * inst_fps
        self._last_frame_t = now
        self.frame_processed.emit(frame, detections, self._fps, self._latency)

    def update_config(self, new_cfg: AppConfig) -> None:
        new_cfg = normalize_speaker_output_config(self._sanitize_uart_config(new_cfg))
        cam_changed = (
            self.cfg.camera.source != new_cfg.camera.source
            or self.cfg.camera.width != new_cfg.camera.width
            or self.cfg.camera.height != new_cfg.camera.height
            or self.cfg.camera.mirror != new_cfg.camera.mirror
            or self.cfg.camera.rotation != new_cfg.camera.rotation
        )
        uart_changed = (
            self.cfg.uart.port != new_cfg.uart.port
            or self.cfg.uart.baud != new_cfg.uart.baud
            or self.cfg.uart.ack_timeout_ms != new_cfg.uart.ack_timeout_ms
            or self.cfg.uart.auto_reconnect != new_cfg.uart.auto_reconnect
            or self.cfg.uart.protocol != new_cfg.uart.protocol
        )
        model_changed = (
            self.cfg.model.path != new_cfg.model.path
            or self.cfg.model.device != new_cfg.model.device
            or self.cfg.model.input_size != new_cfg.model.input_size
            or self.cfg.model.half_precision != new_cfg.model.half_precision
            or self.cfg.model.specialist != new_cfg.model.specialist
        )
        was_running = self.is_camera_running()
        if (cam_changed or model_changed) and was_running:
            self.stop_camera()
        self.cfg = new_cfg
        self._speaker.configure(
            enabled=computer_speaker_enabled(new_cfg),
            cooldown_seconds=new_cfg.speaker.cooldown_seconds,
            voice_gender=new_cfg.speaker.voice_gender,
        )
        save_config(new_cfg, self.config_path)
        if model_changed:
            try:
                new_engine = InferenceEngine(
                    new_cfg.model.path,
                    device=new_cfg.model.device,
                    conf=new_cfg.model.conf_threshold,
                    iou=new_cfg.model.iou_threshold,
                    imgsz=new_cfg.model.input_size,
                    half=new_cfg.model.half_precision,
                    specialist=new_cfg.model.specialist,
                )
                self._engine = new_engine
                if self._pipeline is not None:
                    self._pipeline.engine = new_engine
                self.model_status.emit(True)
            except Exception as e:
                logger.warning("model reload after config failed: {}", e)
                self.model_status.emit(False)
        elif self._engine is not None:
            self._engine.update_thresholds(
                new_cfg.model.conf_threshold, new_cfg.model.iou_threshold
            )
        if self._pipeline is not None:
            update_pipeline_config = getattr(self._pipeline, "update_config", None)
            if callable(update_pipeline_config):
                update_pipeline_config(new_cfg)
            else:
                self._pipeline.cfg = new_cfg
                self._pipeline.update_mappings(new_cfg.mappings)
        if uart_changed:
            self._restart_uart_if_needed()
        if (cam_changed or model_changed) and was_running:
            self.start_camera()
        logger.info(
            "config updated cam_changed={} uart_changed={} model_changed={}",
            cam_changed,
            uart_changed,
            model_changed,
        )

    def test_camera(self, source: str) -> None:
        from app.utils.camera_enum import has_external_camera

        if not source or not has_external_camera():
            self.test_camera_result.emit(
                False,
                "Chưa tìm thấy camera USB. Khi chưa cắm USB, app sẽ giữ màn hình đen.",
            )
            return
        worker = _CamProbe(source)
        worker.done.connect(self.test_camera_result.emit)
        self._track_probe(worker)

    def test_uart_ping(self, port: str, baud: int) -> None:
        if not self._is_usb_uart_port(port):
            self.test_uart_result.emit(False, "Chưa thấy cổng USB/Arduino để test UART.")
            return
        worker = _UartProbe(port, baud, self.cfg.uart.protocol)
        worker.done.connect(self.test_uart_result.emit)
        self._track_probe(worker)

    def test_hardware_command(self, port: str, baud: int, command: str) -> None:
        route = route_for_command(command)
        if route is None:
            self.test_uart_result.emit(False, f"Lệnh phần cứng không hợp lệ: {command}")
            return
        if not self._is_usb_uart_port(port):
            self.test_uart_result.emit(False, "UART OFF, không gửi xuống phần cứng.")
            return
        payload = encode_sort(route.command, 0.99, protocol=self.cfg.uart.protocol).decode("utf-8")
        if self._uart is not None and self._uart.isRunning() and self._uart.is_connected:
            track_id = self._next_uart_test_id
            self._next_uart_test_id -= 1
            self._pending_uart_tests[track_id] = (route.command, payload, port, time.time())
            self._uart.send(track_id, route.command, 0.99)
            return
        worker = _UartProbe(port, baud, self.cfg.uart.protocol, route.command)
        worker.done.connect(self.test_uart_result.emit)
        self._track_probe(worker)

    def test_audio_event(
        self,
        event_key: str,
        output_mode: str = "",
        voice_gender: str = "",
    ) -> None:
        clean_event = str(event_key or "").strip()
        if clean_event == "warning":
            clean_event = "multi_object_warning"
        if clean_event not in AUDIO_EVENT_LABELS:
            self.test_uart_result.emit(False, f"Sự kiện âm thanh không hợp lệ: {clean_event}")
            return
        clean_mode = (
            "computer_speaker"
            if str(output_mode or self.cfg.speaker.output_mode).strip() == "computer_speaker"
            else "hardware"
        )
        clean_gender = normalize_voice_gender(voice_gender or self.cfg.speaker.voice_gender)
        if clean_mode == "computer_speaker":
            ok = self._speaker.preview_event(clean_event, voice_gender=clean_gender)
            if ok:
                label = "giọng nam" if clean_gender == "male" else "giọng nữ"
                self.test_uart_result.emit(True, f"Đã phát thử {label} trên loa laptop.")
            else:
                self.test_uart_result.emit(False, f"Không có file giọng cho lệnh: {clean_event}")
            return

        track = int(AUDIO_EVENT_TRACKS[clean_event])
        if not self.is_uart_connected() or self._uart is None:
            self.test_uart_result.emit(
                False,
                f"UART OFF, chưa thể phát track {track} trên loa phần cứng.",
            )
            return
        sender = getattr(self._uart, "send_audio_test", None)
        if not callable(sender):
            self.test_uart_result.emit(False, "UART hiện tại không hỗ trợ audio-only test.")
            return
        track_id = self._next_uart_test_id
        self._next_uart_test_id -= 1
        payload = f"AUDIO:{track}\n"
        self._pending_uart_tests[track_id] = (
            f"AUDIO:{track}",
            payload,
            self.cfg.uart.port,
            time.time(),
        )
        sender(track_id, track)
        logger.info(
            "desktop hardware audio test event={} track={} port={}",
            clean_event,
            track,
            self.cfg.uart.port,
        )

    def test_laptop_voice(self, command: str) -> None:
        self.test_audio_event(
            command,
            output_mode="computer_speaker",
            voice_gender=self.cfg.speaker.voice_gender,
        )

    def _set_auto_sort_enabled(self, enabled: bool) -> None:
        self._actuation_test_enabled = bool(enabled)
        if self._pipeline is not None:
            self._pipeline.set_hardware_dispatch_enabled(self._actuation_test_enabled)
            self._pipeline.reset_dispatch_state()
        self.actuation_mode_changed.emit(self._actuation_test_enabled)

    def set_actuation_test_mode(self, enabled: bool) -> None:
        requested = bool(enabled)
        if requested:
            reason = ""
            if self._pipeline is None:
                reason = "Model chưa sẵn sàng."
            elif not self.is_camera_running():
                reason = "Camera chưa chạy."
            elif not self.is_uart_connected():
                reason = "UART/Arduino chưa kết nối."
            elif (
                not self.cfg.roi.enabled
                or self.cfg.roi.width <= 0
                or self.cfg.roi.height <= 0
            ):
                reason = "ROI chưa hợp lệ."
            if reason:
                self._set_auto_sort_enabled(False)
                self.test_uart_result.emit(
                    False,
                    f"Chưa thể bật phân loại tự động: {reason}",
                )
                return
        self._set_auto_sort_enabled(requested)
        state = "bật" if requested else "tắt"
        logger.info("desktop automatic sorting {}", state)
        msg = (
            f"Phân loại tự động đã {state}. "
            "Khi trạng thái Sẵn sàng, đặt một vật vào ROI; app sẽ tự nhận diện, "
            "phát âm thanh, đổ rác và chờ khay trống."
        )
        self.test_uart_result.emit(
            True,
            msg,
        )

    def is_actuation_test_mode_enabled(self) -> bool:
        return self._actuation_test_enabled

    def dispatch_status(self) -> str:
        if self._pipeline is None:
            return ""
        return str(getattr(self._pipeline, "dispatch_status", "") or "")

    def auto_sort_state(self) -> str:
        if self._pipeline is None:
            return "WAITING_EMPTY"
        return str(getattr(self._pipeline, "auto_sort_state", "WAITING_EMPTY") or "WAITING_EMPTY")

    def is_uart_connected(self) -> bool:
        return bool(self._uart is not None and self._uart.isRunning() and self._uart.is_connected)

    def refresh_learn_now_status(self, cls_name: str = "") -> None:
        class_name = canonical_class_name(cls_name) or str(cls_name or "").strip()
        if not class_name:
            return
        self._learn_now_request_id += 1
        self._pending_learn_now_class = class_name
        self._start_pending_learn_now_status()

    def _start_pending_learn_now_status(self) -> None:
        if self._learn_now_worker is not None:
            return
        class_name = self._pending_learn_now_class
        if not class_name:
            return
        self._pending_learn_now_class = None
        request_id = self._learn_now_request_id
        worker = _LearnNowStatusWorker(
            request_id,
            self._capture_queue_dir(),
            class_name,
            dataset_db_path(),
        )
        worker.done.connect(self._on_learn_now_status_ready)
        worker.finished.connect(lambda worker=worker: self._on_learn_now_worker_finished(worker))
        worker.finished.connect(worker.deleteLater)
        self._learn_now_worker = worker
        worker.start()

    def _on_learn_now_status_ready(
        self,
        request_id: int,
        status: object,
        error: str,
        elapsed_s: float,
    ) -> None:
        logger.info("learn-now status request={} elapsed_ms={:.0f}", request_id, elapsed_s * 1000)
        if request_id != self._learn_now_request_id:
            return
        if error:
            self.learn_now_action_result.emit(False, f"Không đọc được trạng thái train: {error}")
            return
        self.learn_now_status_changed.emit(status)

    def _on_learn_now_worker_finished(self, worker: _LearnNowStatusWorker) -> None:
        if self._learn_now_worker is worker:
            self._learn_now_worker = None
        self._start_pending_learn_now_status()

    def refresh_learn_now_references(self, cls_name: str = "") -> None:
        if self._pipeline is not None:
            self._pipeline.refresh_manual_references()
        self.refresh_learn_now_status(cls_name)
        clean = canonical_class_name(cls_name) or str(cls_name or "").strip()
        self.learn_now_action_result.emit(True, f"Đã làm mới reference cho {clean or 'class đang chọn'}.")

    def refresh_training_status(self) -> None:
        if self._training_status_worker is not None:
            self._training_status_pending = True
            return
        self._training_status_pending = False
        worker = _TrainingStatusWorker(self._project_root())
        worker.done.connect(self._on_training_status_ready)
        worker.finished.connect(lambda worker=worker: self._on_training_status_worker_finished(worker))
        worker.finished.connect(worker.deleteLater)
        self._training_status_worker = worker
        worker.start()

    def _on_training_status_ready(self, status: object, error: str, elapsed_s: float) -> None:
        logger.info("training status elapsed_ms={:.0f}", elapsed_s * 1000)
        if error:
            logger.warning("training status failed: {}", error)
            return
        self.training_status_changed.emit(status)

    def _on_training_status_worker_finished(self, worker: _TrainingStatusWorker) -> None:
        if self._training_status_worker is worker:
            self._training_status_worker = None
        if self._training_status_pending:
            self.refresh_training_status()

    def start_learn_now_candidate_training(self, cls_name: str, profile: str) -> None:
        class_name = canonical_class_name(cls_name)
        if not class_name:
            self.learn_now_action_result.emit(False, "Chọn class hợp lệ trước khi train.")
            return
        profile = "strong" if str(profile).strip().lower() == "strong" else "micro"
        if self.is_actuation_test_mode_enabled():
            self.learn_now_action_result.emit(
                False,
                "Tắt Bật gửi Arduino trước khi huấn luyện phần mềm.",
            )
            return
        if training_processes():
            self.learn_now_action_result.emit(False, "Đang có training khác chạy.")
            self.refresh_training_status()
            return
        status = build_selected_learn_now_status(
            self._capture_queue_dir(),
            class_name,
            dataset_db_path(),
        )
        selected = status.get("selected") if isinstance(status, dict) else None
        if not isinstance(selected, dict) or not selected.get("ready_for_micro_train"):
            message = str(selected.get("message") if isinstance(selected, dict) else "")
            self.learn_now_action_result.emit(
                False,
                message or "Cần ít nhất 6 ảnh đã duyệt trước khi train nhanh.",
            )
            self.learn_now_status_changed.emit(status)
            return
        if profile == "strong" and not selected.get("ready_for_strong_train"):
            self.learn_now_action_result.emit(
                False,
                "Train mạnh cần ít nhất 24 ảnh đã duyệt và 6 ảnh holdout.",
            )
            self.learn_now_status_changed.emit(status)
            return
        try:
            pid = start_learn_now_training(self._project_root(), class_name, profile)
        except (FileNotFoundError, OSError) as e:
            self.learn_now_action_result.emit(False, str(e))
            return
        self.learn_now_action_result.emit(
            True,
            f"Đã bắt đầu train {profile} candidate cho {class_name} (PID {pid}).",
        )
        self.training_status_changed.emit(
            {
                "running": True,
                "message": f"Đã khởi động training PID {pid}",
                "run_name": f"learn-now-{profile}-{class_name.casefold().replace(' ', '-')}",
                "progress_percent": 0.0,
                "best_model_path": "",
            }
        )
        self.refresh_training_status()

    def stop_learn_now_training(self) -> None:
        stopped = stop_training_processes()
        if stopped:
            self.learn_now_action_result.emit(True, f"Đã dừng training PID: {', '.join(map(str, stopped))}.")
        else:
            self.learn_now_action_result.emit(False, "Không có training đang chạy.")
        self.refresh_training_status()

    def load_candidate_model_for_test(self, path: str) -> None:
        try:
            new_engine = InferenceEngine(
                path,
                device=self.cfg.model.device,
                conf=self.cfg.model.conf_threshold,
                iou=self.cfg.model.iou_threshold,
                imgsz=self.cfg.model.input_size,
                half=self.cfg.model.half_precision,
            )
        except Exception as e:
            self.reload_model_result.emit(False, str(e))
            return
        self._engine = new_engine
        if self._pipeline is not None:
            self._pipeline.engine = new_engine
            self._pipeline.reset_dispatch_state()
        self.model_status.emit(True)
        self.reload_model_result.emit(
            True,
            f"Loaded candidate tạm thời: {len(new_engine.class_names)} classes. Config production chưa đổi.",
        )

    def reload_model(self, path: str) -> None:
        try:
            new_engine = InferenceEngine(
                path,
                device=self.cfg.model.device,
                conf=self.cfg.model.conf_threshold,
                iou=self.cfg.model.iou_threshold,
                imgsz=self.cfg.model.input_size,
                half=self.cfg.model.half_precision,
                specialist=self.cfg.model.specialist,
            )
        except Exception as e:
            self.reload_model_result.emit(False, str(e))
            return
        self._engine = new_engine
        if self._pipeline is not None:
            self._pipeline.engine = new_engine
        self.cfg.model.path = path
        self.reload_model_result.emit(True, f"Loaded {len(new_engine.class_names)} classes")

    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def history(self):
        return self._pipeline.history if self._pipeline is not None else None

    def take_snapshot(self) -> None:
        from datetime import datetime

        import cv2

        from app.utils.paths import snapshots_dir

        if self._last_frame is None:
            self.snapshot_saved.emit(False, "no frame yet")
            return
        ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        out = snapshots_dir() / f"snap-{ts}.jpg"
        try:
            cv2.imwrite(str(out), self._last_frame)
            self.snapshot_saved.emit(True, str(out))
        except Exception as e:
            self.snapshot_saved.emit(False, str(e))

    def import_manual_phone_samples(self, cls_name: str, cls_id: int, files) -> None:
        from app.core.dataset_queue import import_manual_phone_images
        from app.core.waste_categories import default_class_id_for_name
        from app.utils.paths import dataset_db_path

        class_name = canonical_class_name(cls_name)
        class_id = default_class_id_for_name(class_name)
        if not class_name or class_id is None:
            self.snapshot_saved.emit(False, "Nhập nhãn hợp lệ trước khi thêm ảnh thủ công.")
            return
        image_files = [str(path) for path in (files or []) if str(path or "").strip()]
        if not image_files:
            self.snapshot_saved.emit(False, "Chưa chọn ảnh để thêm vào huấn luyện.")
            return
        try:
            added = import_manual_phone_images(
                image_files,
                self._capture_queue_dir(),
                class_name,
                int(class_id if class_id is not None else cls_id),
                catalog_path=dataset_db_path(),
            )
        except Exception as e:
            self.snapshot_saved.emit(False, str(e))
            return
        self.capture_saved.emit(str(self._capture_queue_dir()))
        self.snapshot_saved.emit(
            True,
            f"Đã thêm {added} ảnh {class_name}; cần vẽ bbox và lưu đã duyệt trước khi train.",
        )
        self.refresh_learn_now_status(class_name)

    def capture_camera_sample(self, cls_name: str) -> None:
        from app.core.dataset_queue import import_manual_camera_frame
        from app.core.waste_categories import default_class_id_for_name
        from app.utils.paths import dataset_db_path, resource_path

        cls_name = str(cls_name or "").strip()
        if not cls_name:
            self.snapshot_saved.emit(False, "missing class label")
            return
        if not self.is_camera_running() or self._last_frame is None:
            self.snapshot_saved.emit(False, "Bat camera va cho co frame truoc khi ghi mau train.")
            return
        class_id = default_class_id_for_name(cls_name)
        if class_id is None and self._engine is not None:
            for model_id, model_name in self._engine.class_names.items():
                if str(model_name).casefold() == cls_name.casefold():
                    class_id = int(model_id)
                    break
        if class_id is None:
            class_id = 0
        output_path = Path(self.cfg.capture.output_dir).expanduser()
        if output_path.is_absolute():
            queue_dir = output_path / "low_conf_queue"
        else:
            candidate = Path.cwd() / output_path / "low_conf_queue"
            queue_dir = candidate if candidate.exists() else resource_path(".") / output_path / "low_conf_queue"
        try:
            img_path = import_manual_camera_frame(
                self._last_frame,
                queue_dir,
                cls_name,
                class_id,
                catalog_path=dataset_db_path(),
            )
        except Exception as e:
            self.snapshot_saved.emit(False, str(e))
            return
        self.capture_saved.emit(str(img_path))
        self.snapshot_saved.emit(
            True,
            f"Đã ghi mẫu {cls_name}: {img_path.name}. Mở Web annotate để chỉnh box trước khi train.",
        )

        self.refresh_learn_now_status(cls_name)

    def camera_annotation_snapshot(self, cls_name: str):
        if not self.is_camera_running() or self._last_frame is None:
            return False, "Bật camera và chờ có frame trước khi chụp & gắn nhãn.", None, None
        frame = self._last_frame.copy()
        self._annotation_frame = frame.copy()
        bbox = self._suggest_annotation_bbox(frame, cls_name)
        return True, "", frame, bbox

    def capture_reviewed_camera_sample(
        self,
        cls_name: str,
        cls_id: int,
        xyxy,
        approve_now: bool,
    ) -> None:
        from app.core.dataset_queue import (
            import_manual_camera_frame,
            save_reviewed_camera_annotation,
        )
        from app.utils.paths import dataset_db_path

        cls_name = str(cls_name or "").strip()
        if not cls_name:
            self.snapshot_saved.emit(False, "missing class label")
            return
        frame = self._annotation_frame
        if frame is None and self._last_frame is not None:
            frame = self._last_frame.copy()
        if frame is None:
            self.snapshot_saved.emit(False, "Bật camera và chờ có frame trước khi lưu mẫu.")
            return
        if xyxy is None:
            self.snapshot_saved.emit(False, "Vui lòng vẽ bbox trước khi lưu mẫu.")
            return
        queue_dir = self._capture_queue_dir()
        try:
            if approve_now:
                img_path = save_reviewed_camera_annotation(
                    frame,
                    queue_dir,
                    cls_name,
                    int(cls_id),
                    xyxy,
                    catalog_path=dataset_db_path(),
                )
            else:
                img_path = import_manual_camera_frame(
                    frame,
                    queue_dir,
                    cls_name,
                    int(cls_id),
                    xyxy=xyxy,
                    catalog_path=dataset_db_path(),
                )
        except Exception as e:
            self.snapshot_saved.emit(False, str(e))
            return
        self._annotation_frame = None
        if self._pipeline is not None:
            self._pipeline.refresh_manual_references()
        self.capture_saved.emit(str(img_path))
        state = "đã duyệt/trainable" if approve_now else "cần duyệt"
        self.snapshot_saved.emit(True, f"Đã lưu mẫu {cls_name} ({state}): {img_path.name}.")

        self.refresh_learn_now_status(cls_name)

    def capture_hard_negative_sample(self, reason: str) -> None:
        from app.core.hard_negative_dataset import capture_hard_negative_frame
        from app.utils.paths import dataset_db_path, resource_path

        reason = str(reason or "").strip()
        if not reason:
            self.snapshot_saved.emit(False, "missing hard negative reason")
            return
        if not self.is_camera_running() or self._last_frame is None:
            self.snapshot_saved.emit(False, "Bat camera va cho co frame truoc khi ghi hard negative.")
            return
        output_path = Path(self.cfg.capture.output_dir).expanduser()
        if output_path.is_absolute():
            queue_dir = output_path / "low_conf_queue"
        else:
            candidate = Path.cwd() / output_path / "low_conf_queue"
            queue_dir = candidate if candidate.exists() else resource_path(".") / output_path / "low_conf_queue"
        try:
            img_path = capture_hard_negative_frame(
                self._last_frame,
                queue_dir,
                reason,
                catalog_path=dataset_db_path(),
                extra_meta={"capture_mode": "hard_negative_desktop", "hardware_blocked": True},
            )
        except Exception as e:
            self.snapshot_saved.emit(False, str(e))
            return
        self.capture_saved.emit(str(img_path))
        self.snapshot_saved.emit(True, f"Đã ghi hard negative {reason}: {img_path.name}. Mẫu này không vào train.")

        self.refresh_learn_now_status("")

    def _capture_queue_dir(self) -> Path:
        from app.utils.paths import resource_path

        output_path = Path(self.cfg.capture.output_dir).expanduser()
        if output_path.is_absolute():
            return output_path / "low_conf_queue"
        candidate = Path.cwd() / output_path / "low_conf_queue"
        return candidate if candidate.exists() else resource_path(".") / output_path / "low_conf_queue"

    def _suggest_annotation_bbox(self, frame, cls_name: str) -> tuple[int, int, int, int]:
        from app.core.multi_object_dispatch import foreground_object_boxes
        from app.core.waste_categories import canonical_class_name

        height, width = frame.shape[:2]
        target = canonical_class_name(cls_name) or str(cls_name or "").strip()

        def _area(box: tuple[int, int, int, int]) -> int:
            return max(0, box[2] - box[0]) * max(0, box[3] - box[1])

        detections = list(self._last_detections or [])
        matching = [
            tuple(int(value) for value in det.xyxy)
            for det in detections
            if (canonical_class_name(det.cls_name) or det.cls_name) == target
        ]
        if matching:
            return self._clamp_bbox(max(matching, key=_area), width, height)
        all_boxes = [tuple(int(value) for value in det.xyxy) for det in detections]
        if all_boxes:
            return self._clamp_bbox(max(all_boxes, key=_area), width, height)
        foreground = foreground_object_boxes(
            frame,
            roi=self.cfg.roi,
            min_area_ratio=self.cfg.unknown_fallback.min_area_ratio,
        )
        if foreground:
            return self._clamp_bbox(foreground[0], width, height)
        if self.cfg.roi.enabled and self.cfg.roi.width > 0 and self.cfg.roi.height > 0:
            return self._clamp_bbox(
                (
                    self.cfg.roi.x,
                    self.cfg.roi.y,
                    self.cfg.roi.x + self.cfg.roi.width,
                    self.cfg.roi.y + self.cfg.roi.height,
                ),
                width,
                height,
            )
        return (0, 0, width, height)

    @staticmethod
    def _clamp_bbox(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = box
        left = max(0, min(width, min(int(x1), int(x2))))
        top = max(0, min(height, min(int(y1), int(y2))))
        right = max(0, min(width, max(int(x1), int(x2))))
        bottom = max(0, min(height, max(int(y1), int(y2))))
        if right <= left or bottom <= top:
            return (0, 0, width, height)
        return (left, top, right, bottom)

    def stop(self) -> None:
        self._pending_learn_now_class = None
        self._training_status_pending = False
        for worker in (self._learn_now_worker, self._training_status_worker):
            if worker is None:
                continue
            with suppress(RuntimeError):
                worker.requestInterruption()
            with suppress(RuntimeError):
                worker.wait(10000)
        self._learn_now_worker = None
        self._training_status_worker = None
        self.stop_camera()
        if self._inference_worker is not None:
            worker = self._inference_worker
            self._inference_worker = None
            worker.stop()
            worker.wait(2000)
            worker.deleteLater()
        if self._model_loader is not None:
            self._model_loader.wait(10000)
            if not self._model_loader.isRunning():
                self._model_loader.deleteLater()
            self._model_loader = None
            self._model_loading = False
        for worker in list(self._probes):
            with suppress(RuntimeError):
                worker.requestInterruption()
            with suppress(RuntimeError):
                worker.quit()
            with suppress(RuntimeError):
                if not worker.isRunning() or worker.wait(500):
                    self._forget_probe(worker)
        self._stop_uart_worker()
        if self._pipeline is not None:
            self._pipeline.close()
            self._pipeline = None
        self._pending_camera_start = False
        self._pending_uart_tests.clear()
        self._clear_runtime_buffers()
        logger.info("controller stopped")
