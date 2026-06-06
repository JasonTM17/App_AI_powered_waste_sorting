"""Glue between core workers and UI signals/slots."""

from __future__ import annotations

import time
from contextlib import suppress
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QThread, QTimer, Signal

from app.core.camera import CameraWorker, SharedCameraWorker
from app.core.config import AppConfig, save_config
from app.core.hardware_profile import route_for_command
from app.core.inference import InferenceEngine
from app.core.inference_worker import InferenceWorker
from app.core.pipeline import Pipeline
from app.core.speaker import WasteSpeaker
from app.core.uart import UartWorker
from app.core.uart_protocol import UartProtocol, encode_sort
from app.utils import serial_enum
from app.utils.camera_source import backend_hint, normalize_camera_source
from app.utils.logging import logger
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
                    ok = ok and frame is not None
                cap.release()
                if ok:
                    self.done.emit(True, f"OK ({name})")
                    return
                last_error = f"Cannot open source ({name})"
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


class AppController(QObject):
    camera_status = Signal(bool)
    uart_status = Signal(bool)
    model_status = Signal(bool)
    frame_processed = Signal(object, list, float, float)
    test_camera_result = Signal(bool, str)
    test_uart_result = Signal(bool, str)
    reload_model_result = Signal(bool, str)
    snapshot_saved = Signal(bool, str)
    capture_saved = Signal(str)
    camera_error = Signal(str)

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
            enabled=self.cfg.speaker.enabled,
            cooldown_seconds=self.cfg.speaker.cooldown_seconds,
        )
        self._inference_worker: InferenceWorker | None = None
        self._last_frame_t = 0.0
        self._fps = 0.0
        self._latency = 0.0
        self._last_frame = None
        self._probes: list[QThread] = []
        self._pending_uart_tests: dict[int, tuple[str, str, str, float]] = {}
        self._next_uart_test_id = -1
        self._actuation_test_enabled = False
        self._uart_retry_scheduled = False

    def start(self) -> None:
        self._engine = InferenceEngine(
            self.cfg.model.path,
            device=self.cfg.model.device,
            conf=self.cfg.model.conf_threshold,
            iou=self.cfg.model.iou_threshold,
            imgsz=self.cfg.model.input_size,
            half=self.cfg.model.half_precision,
        )
        self.model_status.emit(True)

        self._pipeline = Pipeline(
            self.cfg,
            self._engine,
            None,
            self.db_path,
            speaker=self._speaker,
        )
        self._configure_camera_dispatch()
        self._pipeline.on_capture_saved = self.capture_saved.emit
        self._start_uart_if_configured()

        self._inference_worker = InferenceWorker(self._pipeline)
        self._inference_worker.processed.connect(self._on_inferred)
        self._inference_worker.start()

        # Camera is no longer auto-started. User opts in from Live page.
        # This avoids holding the camera handle while idle and lets the
        # user tweak Settings before the device is opened.
        self.camera_status.emit(False)
        logger.info("controller started (camera idle)")

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
        if not self._is_usb_uart_port(port):
            if port:
                present, eligible = self._uart_port_presence(port)
                if present and not eligible:
                    logger.info("uart port ignored because it is not USB/Arduino: {}", port)
                    self.cfg.uart.port = ""
                    save_config(self.cfg, self.config_path)
                else:
                    logger.info("uart port {} not visible yet; keeping config and retrying", port)
                    self._schedule_uart_retry()
            if self._pipeline is not None:
                self._pipeline.set_uart(None)
            self.uart_status.emit(False)
            return

        try:
            self._uart_lock = acquire_runtime_lock("uart")
        except RuntimeLockError as e:
            logger.warning("uart start refused: {}", e)
            if self._pipeline is not None:
                self._pipeline.set_uart(None)
            self.uart_status.emit(False)
            self._schedule_uart_retry()
            return
        worker = UartWorker(
            port=port,
            baud=self.cfg.uart.baud,
            ack_timeout_ms=self.cfg.uart.ack_timeout_ms,
            auto_reconnect=self.cfg.uart.auto_reconnect,
            protocol=self.cfg.uart.protocol,
        )
        worker.connected.connect(self.uart_status.emit)
        worker.ack_received.connect(self._on_uart_ack)
        if self._pipeline is not None:
            self._pipeline.set_uart(worker)
        self._uart = worker
        self._uart_retry_scheduled = False
        self._uart.start()
        logger.info("uart start requested port={}", port)

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
            self.uart_status.emit(False)
            return
        worker = self._uart
        self._uart = None
        self._uart_retry_scheduled = False
        with suppress(RuntimeError, TypeError):
            worker.connected.disconnect(self.uart_status.emit)
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
        self.uart_status.emit(False)
        logger.info("uart stopped")

    def _restart_uart_if_needed(self) -> None:
        self._stop_uart_worker()
        self._start_uart_if_configured()

    def _configure_camera_dispatch(self) -> None:
        if self._pipeline is None:
            return
        self._pipeline.set_hardware_dispatch_enabled(self._actuation_test_enabled)

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
        self.camera_error.emit("Camera dang chay qua shared stream tu runtime khac.")
        logger.info("shared camera start requested")

    def stop_camera(self) -> None:
        if self._camera is None:
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
        new_cfg = self._sanitize_uart_config(new_cfg)
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
        )
        was_running = self.is_camera_running()
        if (cam_changed or model_changed) and was_running:
            self.stop_camera()
        self.cfg = new_cfg
        self._speaker.configure(
            enabled=new_cfg.speaker.enabled,
            cooldown_seconds=new_cfg.speaker.cooldown_seconds,
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
        worker.finished.connect(worker.deleteLater)
        self._probes.append(worker)
        worker.start()

    def test_uart_ping(self, port: str, baud: int) -> None:
        if not self._is_usb_uart_port(port):
            self.test_uart_result.emit(False, "Chưa thấy cổng USB/Arduino để test UART.")
            return
        worker = _UartProbe(port, baud, self.cfg.uart.protocol)
        worker.done.connect(self.test_uart_result.emit)
        worker.finished.connect(worker.deleteLater)
        self._probes.append(worker)
        worker.start()

    def test_hardware_command(self, port: str, baud: int, command: str) -> None:
        route = route_for_command(command)
        if route is None:
            self.test_uart_result.emit(False, f"Lenh phan cung khong hop le: {command}")
            return
        if not self._is_usb_uart_port(port):
            self.test_uart_result.emit(False, "UART OFF, khong gui xuong phan cung.")
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
        worker.finished.connect(worker.deleteLater)
        self._probes.append(worker)
        worker.start()

    def set_actuation_test_mode(self, enabled: bool) -> None:
        self._actuation_test_enabled = bool(enabled)
        if self._pipeline is not None:
            self._pipeline.set_hardware_dispatch_enabled(self._actuation_test_enabled)
            self._pipeline.reset_dispatch_state()
        state = "bat" if enabled else "tat"
        logger.info("desktop actuation test mode {}", state)
        msg = (
            f"Actuation Test Mode da {state}. "
            "Bat camera khi khay trong, roi dua tung mau rac vao vung khay de xem class -> bin -> payload -> ACK."
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

    def is_uart_connected(self) -> bool:
        return bool(self._uart is not None and self._uart.isRunning() and self._uart.is_connected)

    def reload_model(self, path: str) -> None:
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
        self.cfg.model.path = path
        self.reload_model_result.emit(True, f"Loaded {len(new_engine.class_names)} classes")

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
            f"Da ghi mau {cls_name}: {img_path.name}. Mo Web annotate de chinh box truoc khi train.",
        )

    def stop(self) -> None:
        if self._camera is not None:
            self._camera.stop()
            self._camera.wait(2000)
            self._camera = None
        if self._camera_lock is not None:
            self._camera_lock.release()
            self._camera_lock = None
        if self._inference_worker is not None:
            self._inference_worker.stop()
            self._inference_worker.wait(2000)
        self._stop_uart_worker()
        if self._pipeline is not None:
            self._pipeline.close()
        logger.info("controller stopped")
