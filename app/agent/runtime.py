"""Thread-based runtime used by the local web agent."""

from __future__ import annotations

import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, RLock, Thread, current_thread
from typing import Any

import numpy as np

from app.agent.schemas import BinFullnessDTO, DetectionDTO, DeviceState, RuntimeStatus
from app.core.capture_session import CaptureSessionManager
from app.core.config import (
    AppConfig,
    ClassMapping,
    computer_speaker_enabled,
    load_config,
    normalize_speaker_output_config,
    save_config,
)
from app.core.dataset_queue import import_manual_camera_frame
from app.core.frame_transform import apply_camera_transform
from app.core.hardware_profile import hardware_profile_payload, route_for_command
from app.core.history import HistoryService
from app.core.inference import InferenceEngine
from app.core.pipeline import Pipeline
from app.core.speaker import WasteSpeaker
from app.core.three_bin_classifier import parse_three_bin_class_name
from app.core.uart_protocol import (
    UartProtocol,
    encode_angle_test,
    encode_audio_test,
    encode_home_test,
    encode_mp3_test,
    encode_ping,
    encode_profile_request,
    encode_sort,
    encode_sort_angle_test,
    expected_ack_command,
    parse_line,
    protocol_expects_ack,
)
from app.core.waste_categories import (
    category_for_bin_index,
    category_for_command,
    normalize_mapping_to_three_bins,
)
from app.utils.camera_enum import list_pnp_cameras, probe_usb_cameras
from app.utils.camera_frame_quality import (
    FrameQuality,
    evaluate_frame_quality,
    frame_quality_diagnostics,
)
from app.utils.camera_source import backend_hint, normalize_camera_source
from app.utils.logging import logger
from app.utils.paths import resource_path
from app.utils.runtime_lock import RuntimeLock, RuntimeLockError, acquire_runtime_lock
from app.utils.serial_enum import (
    is_eligible_usb_serial_port,
    list_serial_ports,
    select_single_usb_serial_port,
)
from app.utils.shared_camera_stream import (
    SharedFramePublisher,
    read_shared_frame,
    shared_frame_diagnostics,
)

STREAM_INFERENCE_INTERVAL_S = 0.15
STREAM_FRAME_INTERVAL_S = 0.05
STREAM_JPEG_MAX_WIDTH = 960
BIN_FULLNESS_STALE_AFTER_S = 10.0
BIN_COUNT = 3
ARDUINO_SERIAL_RESET_SETTLE_S = 2.2


class ThreadUartSender:
    """Small non-Qt UART sender used by FastAPI runtime."""

    def __init__(
        self,
        port: str,
        baud: int,
        ack_timeout_ms: int,
        on_ack,
        on_bin,
        protocol: UartProtocol = "plain_group",
    ):
        self.port = port
        self.baud = baud
        self.ack_timeout_ms = ack_timeout_ms
        self.on_ack = on_ack
        self.on_bin = on_bin
        self.protocol = protocol
        self.expects_ack = protocol_expects_ack(protocol)
        self.connected = False
        self.message = ""
        self.last_pong_at: float | None = None
        self.last_profile: str = ""
        self.last_profile_at: float | None = None
        self.last_log: str = ""
        self.last_ack: dict[str, object] = {}
        self.last_proximity: dict[str, object] = {}
        self.last_audio: dict[str, object] = {}
        self.last_mp3: dict[str, object] = {}
        self.last_mp3_tx: dict[str, object] = {}
        self.last_mp3_rx: dict[str, object] = {}
        self.last_servo: dict[str, object] = {}
        self.disconnect_reason = ""
        self._serial = None
        self._lock = Lock()
        self._responses: Queue[tuple[str, object, object]] = Queue(maxsize=100)
        self._reader_stop = Event()
        self._reader_thread: Thread | None = None
        self._runtime_lock: RuntimeLock | None = None

    def open(self) -> bool:
        try:
            self._runtime_lock = acquire_runtime_lock("uart")
        except RuntimeLockError as e:
            self.message = f"UART đang được runtime khác sử dụng: {e}"
            return False
        try:
            import serial

            self._serial = serial.Serial(self.port, self.baud, timeout=0.1)
            self._reader_stop.clear()
            self._reader_thread = Thread(target=self._reader_loop, daemon=True)
            self._reader_thread.start()
            if self.expects_ack:
                time.sleep(ARDUINO_SERIAL_RESET_SETTLE_S)
                self._serial.write(encode_ping())
                self._serial.write(encode_profile_request())
            self.connected = True
            self.message = f"connected {self.port} ({self.protocol})"
            return True
        except Exception as e:
            self.message = f"open {self.port} failed: {e}"
            self.disconnect_reason = str(e)
            self.connected = False
            self.close()
            return False

    def send(self, track_id, command, conf) -> None:
        if not self.connected or self._serial is None:
            return
        with self._lock:
            t0 = time.time()
            status = "no_ack"
            try:
                self._drain_responses()
                self._serial.write(encode_sort(command, conf, protocol=self.protocol))
                if not self.expects_ack:
                    status = "ok"
                    rtt_ms = int((time.time() - t0) * 1000)
                    try:
                        self.on_ack(track_id, command, status, rtt_ms)
                    except Exception as e:
                        logger.warning("agent uart ack callback failed: {}", e)
                    return
                expected_ack = expected_ack_command(command, self.protocol)
                deadline = t0 + (self.ack_timeout_ms / 1000.0)
                while time.time() < deadline:
                    try:
                        kind, cmd, _payload = self._responses.get(timeout=0.05)
                    except Empty:
                        continue
                    if cmd != expected_ack:
                        continue
                    if kind == "ack":
                        status = "ok"
                        break
                    if kind == "nack":
                        status = "error"
                        break
            except Exception as e:
                status = "error"
                self.message = f"UART write failed: {e}"
                self.disconnect_reason = str(e)
                self.connected = False
            rtt_ms = int((time.time() - t0) * 1000)
            try:
                self.on_ack(track_id, command, status, rtt_ms)
            except Exception as e:
                logger.warning("agent uart ack callback failed: {}", e)

    def send_audio_warning(self, track: int) -> None:
        Thread(
            target=lambda: self.send_audio_test(int(track)),
            name="agent-uart-audio-warning",
            daemon=True,
        ).start()

    def send_test(self, command: str, conf: float = 0.99) -> dict[str, object]:
        payload = encode_sort(command, conf, protocol=self.protocol)
        if not self.connected or self._serial is None:
            return {
                "ok": False,
                "command": command,
                "payload": payload.decode("utf-8"),
                "port": self.port,
                "ack_status": "uart_off",
                "elapsed_ms": 0,
                "message": self.message or "UART OFF, khong gui xuong phan cung.",
            }
        with self._lock:
            t0 = time.time()
            status = "no_ack"
            message = ""
            try:
                self._drain_responses()
                self._serial.write(payload)
                expected_ack = expected_ack_command(command, self.protocol)
                if self.expects_ack:
                    deadline = t0 + (self.ack_timeout_ms / 1000.0)
                    while time.time() < deadline:
                        try:
                            kind, cmd, detail = self._responses.get(timeout=0.05)
                        except Empty:
                            continue
                        if cmd != expected_ack:
                            continue
                        if kind == "ack":
                            status = "ok"
                            break
                        if kind == "nack":
                            status = "error"
                            message = str(detail or "")
                            break
                else:
                    status = "sent"
            except Exception as e:
                status = "error"
                message = f"UART write failed: {e}"
                self.message = message
                self.disconnect_reason = str(e)
                self.connected = False
            elapsed_ms = int((time.time() - t0) * 1000)
        if not message:
            if status == "ok":
                message = f"ACK:{expected_ack_command(command, self.protocol)} from {self.port}"
            elif status == "sent":
                message = f"Sent without ACK wait to {self.port}"
            elif status == "no_ack":
                message = (
                    f"No ACK:{expected_ack_command(command, self.protocol)} "
                    f"within {self.ack_timeout_ms} ms"
                )
        return {
            "ok": status in {"ok", "sent"},
            "command": command,
            "payload": payload.decode("utf-8"),
            "port": self.port,
            "ack_status": status,
            "elapsed_ms": elapsed_ms,
            "message": message,
        }

    def send_angle_test(self, d6_angle: int, d7_angle: int, label: str = "") -> dict[str, object]:
        payload = encode_angle_test(d6_angle, d7_angle)
        expected_ack = f"ANGLE:{int(d6_angle)}:{int(d7_angle)}"
        if not self.connected or self._serial is None:
            return {
                "ok": False,
                "command": "ANGLE",
                "payload": payload.decode("utf-8"),
                "port": self.port,
                "ack_status": "uart_off",
                "elapsed_ms": 0,
                "message": self.message or "UART OFF, khong gui xuong phan cung.",
                "d6": int(d6_angle),
                "d7": int(d7_angle),
                "label": label,
            }
        with self._lock:
            t0 = time.time()
            status = "no_ack"
            message = ""
            try:
                self._drain_responses()
                self._serial.write(payload)
                deadline = t0 + (self.ack_timeout_ms / 1000.0)
                while time.time() < deadline:
                    try:
                        kind, cmd, detail = self._responses.get(timeout=0.05)
                    except Empty:
                        continue
                    if kind == "ack" and cmd == expected_ack:
                        status = "ok"
                        break
                    if kind == "nack" and cmd == "ANGLE":
                        status = "error"
                        message = str(detail or "")
                        break
            except Exception as e:
                status = "error"
                message = f"UART write failed: {e}"
                self.message = message
                self.disconnect_reason = str(e)
                self.connected = False
            elapsed_ms = int((time.time() - t0) * 1000)
        if not message:
            if status == "ok":
                message = f"ACK:{expected_ack} from {self.port}"
            elif status == "no_ack":
                message = f"No ACK:{expected_ack} within {self.ack_timeout_ms} ms"
        return {
            "ok": status == "ok",
            "command": "ANGLE",
            "payload": payload.decode("utf-8"),
            "port": self.port,
            "ack_status": status,
            "elapsed_ms": elapsed_ms,
            "message": message,
            "d6": int(d6_angle),
            "d7": int(d7_angle),
            "label": label,
        }

    def send_home_test(self, d6_angle: int, d7_angle: int, label: str = "") -> dict[str, object]:
        payload = encode_home_test(d6_angle, d7_angle)
        expected_ack = f"HOME:{int(d6_angle)}:{int(d7_angle)}"
        if not self.connected or self._serial is None:
            return {
                "ok": False,
                "command": "HOME",
                "payload": payload.decode("utf-8"),
                "port": self.port,
                "ack_status": "uart_off",
                "elapsed_ms": 0,
                "message": self.message or "UART OFF, khong gui xuong phan cung.",
                "d6": int(d6_angle),
                "d7": int(d7_angle),
                "label": label,
            }
        with self._lock:
            t0 = time.time()
            status = "no_ack"
            message = ""
            try:
                self._drain_responses()
                self._serial.write(payload)
                deadline = t0 + (self.ack_timeout_ms / 1000.0)
                while time.time() < deadline:
                    try:
                        kind, cmd, detail = self._responses.get(timeout=0.05)
                    except Empty:
                        continue
                    if kind == "ack" and cmd == expected_ack:
                        status = "ok"
                        break
                    if kind == "nack" and cmd == "HOME":
                        status = "error"
                        message = str(detail or "")
                        break
            except Exception as e:
                status = "error"
                message = f"UART write failed: {e}"
                self.message = message
                self.disconnect_reason = str(e)
                self.connected = False
            elapsed_ms = int((time.time() - t0) * 1000)
        if not message:
            if status == "ok":
                message = f"ACK:{expected_ack} from {self.port}"
            elif status == "no_ack":
                message = f"No ACK:{expected_ack} within {self.ack_timeout_ms} ms"
        return {
            "ok": status == "ok",
            "command": "HOME",
            "payload": payload.decode("utf-8"),
            "port": self.port,
            "ack_status": status,
            "elapsed_ms": elapsed_ms,
            "message": message,
            "d6": int(d6_angle),
            "d7": int(d7_angle),
            "label": label,
        }

    def send_sort_angle_test(self, command: str, d6_angle: int, d7_angle: int, label: str = "") -> dict[str, object]:
        command = command.strip().upper()
        payload = encode_sort_angle_test(command, d6_angle, d7_angle)
        expected_ack = f"SORTTEST:{command}:{int(d6_angle)}:{int(d7_angle)}"
        if not self.connected or self._serial is None:
            return {
                "ok": False,
                "command": "SORTTEST",
                "route_command": command,
                "payload": payload.decode("utf-8"),
                "port": self.port,
                "ack_status": "uart_off",
                "elapsed_ms": 0,
                "message": self.message or "UART OFF, khong gui xuong phan cung.",
                "d6": int(d6_angle),
                "d7": int(d7_angle),
                "label": label,
            }
        with self._lock:
            t0 = time.time()
            status = "no_ack"
            message = ""
            try:
                self._drain_responses()
                self._serial.write(payload)
                deadline = t0 + (self.ack_timeout_ms / 1000.0)
                while time.time() < deadline:
                    try:
                        kind, cmd, detail = self._responses.get(timeout=0.05)
                    except Empty:
                        continue
                    if kind == "ack" and cmd == expected_ack:
                        status = "ok"
                        break
                    if kind == "nack" and cmd == "SORTTEST":
                        status = "error"
                        message = str(detail or "")
                        break
            except Exception as e:
                status = "error"
                message = f"UART write failed: {e}"
                self.message = message
                self.disconnect_reason = str(e)
                self.connected = False
            elapsed_ms = int((time.time() - t0) * 1000)
        if not message:
            if status == "ok":
                message = f"ACK:{expected_ack} from {self.port}"
            elif status == "no_ack":
                message = f"No ACK:{expected_ack} within {self.ack_timeout_ms} ms"
        return {
            "ok": status == "ok",
            "command": "SORTTEST",
            "route_command": command,
            "payload": payload.decode("utf-8"),
            "port": self.port,
            "ack_status": status,
            "elapsed_ms": elapsed_ms,
            "message": message,
            "d6": int(d6_angle),
            "d7": int(d7_angle),
            "label": label,
        }

    def send_audio_test(self, track: int) -> dict[str, object]:
        track = int(track)
        payload = encode_audio_test(track)
        expected_ack = f"AUDIO:{track}"
        if not self.connected or self._serial is None:
            return {
                "ok": False,
                "track": track,
                "payload": payload.decode("utf-8"),
                "port": self.port,
                "ack_status": "uart_off",
                "elapsed_ms": 0,
                "message": self.message or "UART OFF, khong gui xuong phan cung.",
            }
        with self._lock:
            t0 = time.time()
            status = "no_ack"
            message = ""
            try:
                self._drain_responses()
                self._serial.write(payload)
                deadline = t0 + (self.ack_timeout_ms / 1000.0)
                while time.time() < deadline:
                    try:
                        kind, cmd, detail = self._responses.get(timeout=0.05)
                    except Empty:
                        continue
                    if kind == "ack" and cmd == expected_ack:
                        status = "ok"
                        break
                    if kind == "nack" and cmd == "AUDIO":
                        status = "error"
                        message = str(detail or "")
                        break
            except Exception as e:
                status = "error"
                message = f"UART write failed: {e}"
                self.message = message
                self.disconnect_reason = str(e)
                self.connected = False
            elapsed_ms = int((time.time() - t0) * 1000)
        if not message:
            if status == "ok":
                message = f"ACK:{expected_ack} from {self.port}"
            elif status == "no_ack":
                message = f"No ACK:{expected_ack} within {self.ack_timeout_ms} ms"
        return {
            "ok": status == "ok",
            "track": track,
            "payload": payload.decode("utf-8"),
            "port": self.port,
            "ack_status": status,
            "elapsed_ms": elapsed_ms,
            "message": message,
        }

    def send_mp3_test(self, command: str, value: int | None = None) -> dict[str, object]:
        command = command.strip().upper()
        payload = encode_mp3_test(command, value)
        if command in {"PRIMARY", "MODE_PRIMARY"}:
            command = "MODE_PRIMARY"
        elif command in {"REVERSE", "MODE_REVERSE"}:
            command = "MODE_REVERSE"
        elif command in {"MODE", "MODE_QUERY"}:
            command = "MODE_QUERY"

        if command == "VOL":
            expected_ack = f"MP3:VOL:{int(value)}"
        elif command == "PLAY":
            expected_ack = f"MP3:PLAY:{int(value)}"
        elif command == "PLAYVOL":
            expected_ack = f"MP3:PLAYVOL:{int(value)}"
        elif command == "MODE_PRIMARY":
            expected_ack = "MP3:MODE:PRIMARY"
        elif command == "MODE_REVERSE":
            expected_ack = "MP3:MODE:REVERSE"
        elif command == "MODE_QUERY":
            expected_ack = "MP3:MODE"
        else:
            expected_ack = f"MP3:{command}"
        if not self.connected or self._serial is None:
            return {
                "ok": False,
                "command": command,
                "value": value,
                "payload": payload.decode("utf-8"),
                "port": self.port,
                "ack_status": "uart_off",
                "elapsed_ms": 0,
                "message": self.message or "UART OFF, khong gui xuong phan cung.",
            }
        with self._lock:
            t0 = time.time()
            status = "no_ack"
            message = ""
            try:
                self._drain_responses()
                self._serial.write(payload)
                deadline = t0 + (self.ack_timeout_ms / 1000.0)
                while time.time() < deadline:
                    try:
                        kind, cmd, detail = self._responses.get(timeout=0.05)
                    except Empty:
                        continue
                    if kind == "ack" and (
                        cmd == expected_ack
                        or (command == "MODE_QUERY" and str(cmd or "").startswith("MP3:MODE:"))
                    ):
                        status = "ok"
                        break
                    if kind == "nack" and str(cmd or "").startswith("MP3"):
                        status = "error"
                        message = str(detail or "")
                        break
            except Exception as e:
                status = "error"
                message = f"UART write failed: {e}"
                self.message = message
                self.disconnect_reason = str(e)
                self.connected = False
            elapsed_ms = int((time.time() - t0) * 1000)
        if not message:
            if status == "ok":
                message = f"ACK:{expected_ack} from {self.port}"
            elif status == "no_ack":
                message = f"No ACK:{expected_ack} within {self.ack_timeout_ms} ms"
        return {
            "ok": status == "ok",
            "command": command,
            "value": value,
            "payload": payload.decode("utf-8"),
            "port": self.port,
            "ack_status": status,
            "elapsed_ms": elapsed_ms,
            "message": message,
        }

    def _reader_loop(self) -> None:
        while not self._reader_stop.is_set():
            if self._serial is None:
                break
            try:
                raw = self._serial.readline()
            except Exception as e:
                if not self._reader_stop.is_set():
                    self.message = f"UART read failed: {e}"
                    self.disconnect_reason = str(e)
                    self.connected = False
                break
            if not raw:
                continue
            parsed = parse_line(raw)
            if parsed is None:
                continue
            kind, value, payload = parsed
            if kind == "bin":
                try:
                    self.on_bin(int(value), int(payload))
                except Exception as e:
                    logger.warning("agent bin sensor callback failed: {}", e)
                continue
            if kind == "proximity":
                self.last_proximity = {
                    "command": str(value or ""),
                    "at": time.time(),
                }
                logger.info("agent uart proximity: {}", value)
                continue
            if kind == "audio":
                audio_payload = payload if isinstance(payload, dict) else {}
                self.last_audio = {
                    "command": str(value or ""),
                    "track": audio_payload.get("track"),
                    "source": audio_payload.get("source"),
                    "at": time.time(),
                }
                logger.info("agent uart audio: {}", self.last_audio)
                continue
            if kind == "mp3":
                self.last_mp3 = {
                    "event": str(value or ""),
                    "detail": payload,
                    "at": time.time(),
                }
                if value == "tx":
                    self.last_mp3_tx = dict(self.last_mp3)
                elif value == "rx":
                    self.last_mp3_rx = dict(self.last_mp3)
                logger.info("agent uart mp3: {}", self.last_mp3)
                continue
            if kind == "servo":
                self.last_servo = {
                    "event": str(value or ""),
                    "detail": payload,
                    "at": time.time(),
                }
                logger.info("agent uart servo: {}", self.last_servo)
                continue
            if kind == "profile":
                self.last_profile = str(value or "")
                self.last_profile_at = time.time()
                self.message = f"connected {self.port} ({self.protocol}); {self.last_profile}"
                continue
            if kind == "log":
                self.last_log = str(payload or "")
                logger.info("agent uart log: {}", payload)
                continue
            if kind == "pong":
                self.last_pong_at = time.time()
                self.message = f"connected {self.port} ({self.protocol})"
                continue
            if kind in {"ack", "nack"}:
                self.last_ack = {
                    "kind": kind,
                    "command": value,
                    "detail": payload,
                    "at": time.time(),
                }
                try:
                    self._responses.put_nowait((kind, value, payload))
                except Exception:
                    with suppress(Empty):
                        self._responses.get_nowait()
                    with suppress(Exception):
                        self._responses.put_nowait((kind, value, payload))

    def _drain_responses(self) -> None:
        while True:
            try:
                self._responses.get_nowait()
            except Empty:
                return

    def close(self) -> None:
        self._reader_stop.set()
        if self._serial is not None:
            with suppress(Exception):
                self._serial.close()
        self._serial = None
        if (
            self._reader_thread is not None
            and self._reader_thread.is_alive()
            and current_thread() is not self._reader_thread
        ):
            self._reader_thread.join(timeout=1)
        self._reader_thread = None
        self.connected = False
        if self._runtime_lock is not None:
            self._runtime_lock.release()
            self._runtime_lock = None


class AgentRuntime:
    """Owns hardware handles for the web agent."""

    def __init__(
        self,
        config_file: Path,
        history_file: Path,
        dataset_file: Path,
        operations_file: Path | None = None,
    ):
        self.config_file = config_file
        self.history_file = history_file
        self.dataset_file = dataset_file
        self.operations_file = operations_file or history_file.with_name("operations.db")
        self.cfg = load_config(config_file)
        self._state_lock = RLock()
        self._camera_stop = Event()
        self._camera_thread: Thread | None = None
        self._inference_thread: Thread | None = None
        self._camera_lock: RuntimeLock | None = None
        self._camera_shared_mode = False
        self._shared_publisher = SharedFramePublisher()
        self._latest_jpeg = _black_jpeg()
        self._latest_frame: np.ndarray | None = None
        self._latest_frame_id = 0
        self._latest_jpeg_frame_id = 0
        self._fps = 0.0
        self._latency_ms = 0.0
        self._last_frame_at = 0.0
        self._camera_connected = False
        self._camera_message = "Camera idle"
        self._camera_diagnostics: dict[str, object] = {
            "mode": "idle",
            "source": "",
            "usable": False,
            "black_frame": True,
            "reason": "Camera idle",
        }
        self._model_message = ""
        self._detections: list[DetectionDTO] = []
        self._bin_readings: dict[int, tuple[int, float, str]] = {}
        self._actuation_test_enabled = False
        self._engine: InferenceEngine | None = None
        self._pipeline: Pipeline | None = None
        self._uart: ThreadUartSender | None = None
        self._speaker = WasteSpeaker(
            enabled=computer_speaker_enabled(self.cfg),
            cooldown_seconds=self.cfg.speaker.cooldown_seconds,
        )
        self._model_class_cache: dict[int, str] | None = None
        self._capture_session = CaptureSessionManager(
            self._queue_dir_for_config(self.cfg),
            self.dataset_file,
        )
        self._device_scan_lock = Lock()
        self._device_cache_at = 0.0
        self._device_cache_ttl = 5.0
        self._cached_usb_cameras: list[dict] = []
        self._cached_serial_ports: list[dict] = []
        self._uart_warning = ""
        self._restart_uart_from_config()

    def status(self, *, include_devices: bool = True) -> RuntimeStatus:
        usb_cameras: list[dict] = []
        serial_ports: list[dict] = []
        if include_devices:
            usb_cameras, serial_ports = self._device_snapshot()
        with self._state_lock:
            model_path = resource_path(self.cfg.model.path)
            model_ok = self._engine is not None or model_path.exists()
            model_msg = self._model_message or (str(model_path) if model_ok else "Model missing")
            three_bin = self._three_bin_status_locked()
            uart_running = self._uart is not None
            uart_connected = self._uart.connected if self._uart is not None else False
            uart_msg = self._uart.message if self._uart is not None else self._uart_warning or "UART off"
            camera_running = self._camera_thread is not None and self._camera_thread.is_alive()
            current_source = ""
            if camera_running:
                current_source = "shared-camera" if self._camera_shared_mode else self.cfg.camera.source
            camera_diagnostics = dict(self._camera_diagnostics)
            if self._last_frame_at:
                camera_diagnostics["frame_age_s"] = round(max(0.0, time.time() - self._last_frame_at), 2)
            return RuntimeStatus(
                camera=DeviceState(
                    connected=self._camera_connected,
                    running=camera_running,
                    message=self._camera_message,
                ),
                uart=DeviceState(
                    connected=uart_connected,
                    running=uart_running,
                    message=uart_msg,
                ),
                model=DeviceState(connected=model_ok, running=self._engine is not None, message=model_msg),
                three_bin_classifier=DeviceState(
                    connected=bool(three_bin.get("ready")),
                    running=bool(three_bin.get("enabled")),
                    message=str(three_bin.get("message") or ""),
                ),
                camera_diagnostics=camera_diagnostics,
                fps=round(self._fps, 2),
                latency_ms=round(self._latency_ms, 2),
                current_source=current_source,
                current_port=self.cfg.uart.port,
                usb_cameras=usb_cameras,
                serial_ports=serial_ports,
            )

    def refresh_devices(self) -> RuntimeStatus:
        with self._state_lock:
            self._device_cache_at = 0.0
            self._cached_usb_cameras = []
            self._cached_serial_ports = []
        return self.status()

    def _three_bin_status_locked(self) -> dict[str, object]:
        if self._pipeline is not None:
            return self._pipeline.three_bin_classifier_status()
        cfg = self.cfg.three_bin_classifier
        path = resource_path(cfg.model_path)
        return {
            "enabled": cfg.enabled,
            "ready": False,
            "model_path": str(path),
            "exists": path.exists(),
            "message": "ready after pipeline load" if cfg.enabled and path.exists() else "disabled" if not cfg.enabled else "missing artifact",
        }

    def hardware_profile(self) -> dict[str, object]:
        payload = hardware_profile_payload()
        payload["current_port"] = self.cfg.uart.port
        payload["uart_message"] = self.status(include_devices=False).uart.message
        return payload

    def hardware_diagnostics(self) -> dict[str, object]:
        status = self.status(include_devices=True)
        now = time.time()
        uart = self._uart
        vo_co_route = route_for_command("R")
        tai_che_route = route_for_command("I")
        return {
            "selected_port": self.cfg.uart.port,
            "uart_running": status.uart.running,
            "uart_connected": status.uart.connected,
            "uart_message": status.uart.message,
            "eligible_ports": [
                port for port in status.serial_ports if bool(port.get("is_usb"))
            ],
            "firmware_profile": uart.last_profile if uart is not None else "",
            "firmware_profile_age_s": _age_seconds(now, uart.last_profile_at if uart else None),
            "last_pong_age_s": _age_seconds(now, uart.last_pong_at if uart else None),
            "last_ack": dict(uart.last_ack) if uart is not None else {},
            "last_proximity": dict(uart.last_proximity) if uart is not None else {},
            "last_audio": dict(uart.last_audio) if uart is not None else {},
            "last_mp3": dict(uart.last_mp3) if uart is not None else {},
            "last_mp3_tx": dict(uart.last_mp3_tx) if uart is not None else {},
            "last_mp3_rx": dict(uart.last_mp3_rx) if uart is not None else {},
            "last_servo": dict(getattr(uart, "last_servo", {})) if uart is not None else {},
            "audio_protocol": "open_smart_serial_mp3_a",
            "current_home": hardware_profile_payload()["servo"].get("wait_degrees", {}),
            "current_inorganic": vo_co_route.servo_positions if vo_co_route is not None else {},
            "current_vo_co": vo_co_route.servo_positions if vo_co_route is not None else {},
            "current_tai_che": tai_che_route.servo_positions if tai_che_route is not None else {},
            "last_log": uart.last_log if uart is not None else "",
            "disconnect_reason": uart.disconnect_reason if uart is not None else self._uart_warning,
            "warning": "" if status.uart.connected else "UART OFF, khong gui xuong phan cung",
        }

    def reconnect_hardware(self) -> dict[str, object]:
        self._restart_uart_from_config()
        if self._uart is not None and self._uart.connected and self._uart._serial is not None:
            with suppress(Exception):
                self._uart._serial.write(encode_ping())
                self._uart._serial.write(encode_profile_request())
            time.sleep(0.25)
        return self.hardware_diagnostics()

    def test_hardware(self, command: str) -> dict[str, object]:
        command = command.strip().upper()
        route = route_for_command(command)
        if route is None:
            raise ValueError("Unsupported hardware command")
        if self._uart is None or not self._uart.connected:
            self._restart_uart_from_config()
        if self._uart is None:
            return {
                "ok": False,
                "command": command,
                "payload": f"{route.serial_payload}\n",
                "port": self.cfg.uart.port,
                "ack_status": "uart_off",
                "elapsed_ms": 0,
                "message": self._uart_warning or "UART OFF, khong gui xuong phan cung.",
            }
        return self._uart.send_test(command)

    def test_audio(self, track: int) -> dict[str, object]:
        track = int(track)
        if self._uart is None or not self._uart.connected:
            self._restart_uart_from_config()
        if self._uart is None:
            return {
                "ok": False,
                "track": track,
                "payload": f"AUDIO:{track}\n",
                "port": self.cfg.uart.port,
                "ack_status": "uart_off",
                "elapsed_ms": 0,
                "message": self._uart_warning or "UART OFF, khong gui xuong phan cung.",
            }
        return self._uart.send_audio_test(track)

    def test_mp3(self, command: str, value: int | None = None) -> dict[str, object]:
        command = command.strip().upper()
        if self._uart is None or not self._uart.connected:
            self._restart_uart_from_config()
        if self._uart is None:
            payload = encode_mp3_test(command, value).decode("utf-8")
            return {
                "ok": False,
                "command": command,
                "value": value,
                "payload": payload,
                "port": self.cfg.uart.port,
                "ack_status": "uart_off",
                "elapsed_ms": 0,
                "message": self._uart_warning or "UART OFF, khong gui xuong phan cung.",
            }
        return self._uart.send_mp3_test(command, value)

    def test_servo_angles(self, d6_angle: int, d7_angle: int, label: str = "") -> dict[str, object]:
        if self._uart is None or not self._uart.connected:
            self._restart_uart_from_config()
        if self._uart is None:
            return {
                "ok": False,
                "command": "ANGLE",
                "payload": f"ANGLE:{int(d6_angle)}:{int(d7_angle)}\n",
                "port": self.cfg.uart.port,
                "ack_status": "uart_off",
                "elapsed_ms": 0,
                "message": self._uart_warning or "UART OFF, khong gui xuong phan cung.",
                "d6": int(d6_angle),
                "d7": int(d7_angle),
                "label": label,
            }
        return self._uart.send_angle_test(d6_angle, d7_angle, label)

    def test_home_angles(self, d6_angle: int, d7_angle: int, label: str = "") -> dict[str, object]:
        if self._uart is None or not self._uart.connected:
            self._restart_uart_from_config()
        if self._uart is None:
            return {
                "ok": False,
                "command": "HOME",
                "payload": f"HOME:{int(d6_angle)}:{int(d7_angle)}\n",
                "port": self.cfg.uart.port,
                "ack_status": "uart_off",
                "elapsed_ms": 0,
                "message": self._uart_warning or "UART OFF, khong gui xuong phan cung.",
                "d6": int(d6_angle),
                "d7": int(d7_angle),
                "label": label,
            }
        return self._uart.send_home_test(d6_angle, d7_angle, label)

    def test_sort_angles(
        self,
        command: str,
        d6_angle: int,
        d7_angle: int,
        label: str = "",
    ) -> dict[str, object]:
        command = command.strip().upper()
        route = route_for_command(command)
        if route is None:
            raise ValueError("Unsupported hardware command")
        if self._uart is None or not self._uart.connected:
            self._restart_uart_from_config()
        if self._uart is None:
            return {
                "ok": False,
                "command": "SORTTEST",
                "route_command": command,
                "payload": f"SORTTEST:{command}:{int(d6_angle)}:{int(d7_angle)}\n",
                "port": self.cfg.uart.port,
                "ack_status": "uart_off",
                "elapsed_ms": 0,
                "message": self._uart_warning or "UART OFF, khong gui xuong phan cung.",
                "d6": int(d6_angle),
                "d7": int(d7_angle),
                "label": label,
            }
        return self._uart.send_sort_angle_test(command, d6_angle, d7_angle, label)

    def actuation_test_mode(self) -> dict[str, object]:
        status = self.status(include_devices=False)
        uart_connected = status.uart.connected
        warning = "" if uart_connected else "UART OFF, khong gui xuong phan cung"
        with self._state_lock:
            enabled = self._actuation_test_enabled
        return {
            "enabled": enabled,
            "uart_connected": uart_connected,
            "warning": warning,
            "evidence": self.actuation_evidence(limit=3),
        }

    def set_actuation_test_mode(self, enabled: bool) -> dict[str, object]:
        if enabled and self._capture_session.active:
            state = self.actuation_test_mode()
            state["warning"] = "Capture session active; Actuation Test Mode remains off"
            return state
        with self._state_lock:
            self._actuation_test_enabled = bool(enabled)
            pipeline = self._pipeline
        if pipeline is not None:
            pipeline.set_hardware_dispatch_enabled(bool(enabled))
            pipeline.reset_dispatch_state()
        state = "enabled" if enabled else "disabled"
        logger.info("actuation test mode {}", state)
        return self.actuation_test_mode()

    def _force_actuation_off_for_camera_fault(self) -> None:
        with self._state_lock:
            self._actuation_test_enabled = False
            pipeline = self._pipeline
        if pipeline is not None:
            pipeline.set_hardware_dispatch_enabled(False)
            pipeline.reset_dispatch_state()

    def actuation_evidence(self, limit: int = 3) -> list[dict[str, object]]:
        service = HistoryService(self.history_file)
        try:
            rows = service.query(limit=limit)
        finally:
            service.close()
        evidence: list[dict[str, object]] = []
        for row in rows:
            command = str(row.uart_command or "").strip().upper() or None
            route = route_for_command(command or "") if command else None
            ack_status = getattr(row, "ack_status", None)
            evidence.append(
                {
                    "history_id": int(row.id),
                    "timestamp": str(row.ts),
                    "detected_class": str(row.cls_name),
                    "confidence": float(row.conf),
                    "route_label": getattr(row, "route_label", None),
                    "bin_index": getattr(row, "bin_index", None),
                    "command": command,
                    "serial_payload": route.payload_line if route is not None else None,
                    "uart_sent": ack_status not in {None, "uart_off", "capture_failed"},
                    "ack_status": ack_status,
                    "rtt_ms": getattr(row, "rtt_ms", None),
                }
            )
        return evidence

    def model_classes(self) -> dict[int, str]:
        with self._state_lock:
            if self._engine is not None:
                return {int(k): str(v) for k, v in self._engine.class_names.items()}
            if self._model_class_cache is not None:
                return dict(self._model_class_cache)
        try:
            from ultralytics import YOLO

            model_path = resource_path(self.cfg.model.path)
            model = YOLO(str(model_path))
            names = {int(k): str(v) for k, v in dict(model.names).items()}
        except Exception as e:
            logger.warning("agent model class scan failed: {}", e)
            names = {idx: mapping.class_name for idx, mapping in enumerate(self.cfg.mappings)}
        with self._state_lock:
            self._model_class_cache = dict(names)
        return names

    def update_config(self, cfg: AppConfig) -> AppConfig:
        cfg = self._sanitize_config(cfg)
        was_running = self.is_camera_running()
        model_changed = (
            self.cfg.model.path != cfg.model.path
            or self.cfg.model.device != cfg.model.device
            or self.cfg.model.input_size != cfg.model.input_size
            or self.cfg.model.half_precision != cfg.model.half_precision
        )
        if was_running:
            self.stop_camera()
        with self._state_lock:
            self.cfg = cfg
            self._model_class_cache = None
            self._speaker.configure(
                enabled=computer_speaker_enabled(cfg),
                cooldown_seconds=cfg.speaker.cooldown_seconds,
            )
            if self._pipeline is not None:
                self._pipeline.update_config(cfg)
            if model_changed:
                self._reset_pipeline_locked()
        save_config(cfg, self.config_file)
        self._restart_uart_from_config()
        if was_running:
            self.start_camera()
        return cfg

    def update_mappings(self, mappings) -> AppConfig:
        cfg = self.cfg.model_copy(deep=True)
        cfg.mappings = mappings
        return self.update_config(cfg)

    def is_camera_running(self) -> bool:
        return self._camera_thread is not None and self._camera_thread.is_alive()

    def start_camera(self) -> tuple[bool, str]:
        if self.is_camera_running():
            return True, "Camera already running"

        self._force_actuation_off_for_camera_fault()
        probes = probe_usb_cameras()
        usb_source = next((str(item.get("source") or "") for item in probes if item.get("usable")), "")
        if not usb_source:
            shared_diag = shared_frame_diagnostics()
            if read_shared_frame() is not None:
                self._start_shared_camera_mode("Direct USB camera unavailable")
                return True, "Camera shared from another local runtime"
            reason = _camera_probe_failure_reason(probes, shared_diag)
            with self._state_lock:
                self.cfg.camera.source = ""
                self._latest_jpeg = _black_jpeg()
                self._latest_frame = None
                self._latest_frame_id += 1
                self._latest_jpeg_frame_id = self._latest_frame_id
                self._camera_connected = False
                self._camera_message = reason
                self._camera_diagnostics = {
                    "mode": "probe",
                    "source": "",
                    "usable": False,
                    "black_frame": True,
                    "reason": reason,
                    "probes": probes[:6],
                    "shared": shared_diag,
                }
                self._camera_message = reason
                self._camera_message = "Không tìm thấy camera USB; màn hình giữ màu đen"
                self._camera_message = reason
                self._fps = 0.0
                self._latency_ms = 0.0
                self._detections = []
            save_config(self.cfg, self.config_file)
            return False, reason
            return False, "Không tìm thấy camera USB"

        try:
            self._camera_lock = acquire_runtime_lock("camera")
        except RuntimeLockError as e:
            msg = f"Camera USB đang được runtime khác sử dụng: {e}"
            self._start_shared_camera_mode(msg)
            return True, "Camera shared from desktop runtime"

        self.cfg.camera.source = usb_source
        save_config(self.cfg, self.config_file)
        self._camera_stop.clear()
        self._camera_shared_mode = False
        with self._state_lock:
            self._last_frame_at = 0.0
            self._fps = 0.0
            self._latency_ms = 0.0
            self._camera_diagnostics = {
                "mode": "direct",
                "source": usb_source,
                "usable": False,
                "black_frame": True,
                "reason": "opening",
            }
        self._camera_thread = Thread(target=self._camera_loop, args=(usb_source,), daemon=True)
        self._inference_thread = Thread(target=self._inference_loop, daemon=True)
        self._camera_thread.start()
        self._inference_thread.start()
        with self._state_lock:
            self._camera_message = f"Opening {usb_source}"
        return True, f"Camera started: {usb_source}"

    def _start_shared_camera_mode(self, reason: str) -> None:
        self._camera_stop.clear()
        self._camera_shared_mode = True
        with self._state_lock:
            self._last_frame_at = 0.0
            self._fps = 0.0
            self._latency_ms = 0.0
            self._camera_connected = False
            self._camera_message = f"Waiting for desktop shared camera: {reason}"
            self._detections = []
        self._camera_thread = Thread(target=self._shared_camera_loop, daemon=True)
        self._inference_thread = Thread(target=self._inference_loop, daemon=True)
        self._camera_thread.start()
        self._inference_thread.start()

    def stop_camera(self) -> tuple[bool, str]:
        self._camera_stop.set()
        if self._camera_thread is not None:
            self._camera_thread.join(timeout=3)
            self._camera_thread = None
        if self._inference_thread is not None:
            self._inference_thread.join(timeout=3)
            self._inference_thread = None
        self._release_camera_lock()
        self._camera_shared_mode = False
        with self._state_lock:
            self.cfg.camera.source = ""
            self._camera_connected = False
            self._camera_message = "Camera stopped"
            self._camera_diagnostics = {
                "mode": "idle",
                "source": "",
                "usable": False,
                "black_frame": True,
                "reason": "Camera stopped",
            }
            self._latest_jpeg = _black_jpeg()
            self._latest_frame = None
            self._latest_frame_id += 1
            self._latest_jpeg_frame_id = self._latest_frame_id
            self._fps = 0.0
            self._last_frame_at = 0.0
            self._latency_ms = 0.0
            self._detections = []
        save_config(self.cfg, self.config_file)
        return True, "Camera stopped"

    def latest_jpeg(self) -> bytes:
        with self._state_lock:
            cached = bytes(self._latest_jpeg)
            frame = None if self._latest_frame is None else self._latest_frame.copy()
            frame_id = self._latest_frame_id
            encoded_id = self._latest_jpeg_frame_id
        if frame is None or frame_id == encoded_id:
            return cached
        jpeg = _encode_jpeg(frame, max_width=STREAM_JPEG_MAX_WIDTH)
        with self._state_lock:
            if frame_id >= self._latest_jpeg_frame_id:
                self._latest_jpeg = jpeg
                self._latest_jpeg_frame_id = frame_id
                return bytes(self._latest_jpeg)
        return jpeg

    def capture_camera_sample(
        self,
        cls_name: str,
        cls_id: int,
        *,
        use_latest_detection_box: bool = True,
    ) -> Path:
        class_name = str(cls_name or "").strip()
        if not class_name:
            raise ValueError("cls_name is required")
        with self._state_lock:
            if not self.is_camera_running() or self._latest_frame is None:
                raise RuntimeError("Camera is not running or has no frame yet")
            frame = self._latest_frame.copy()
            detections = list(self._detections)
            cfg = self.cfg.model_copy(deep=True)
        bbox = None
        if use_latest_detection_box and detections:
            bbox = tuple(int(value) for value in detections[0].bbox)
        return import_manual_camera_frame(
            frame,
            self._queue_dir_for_config(cfg),
            class_name,
            int(cls_id),
            xyxy=bbox,
            catalog_path=self.dataset_file,
        )

    def capture_unknown_learn_sample(
        self,
        cls_name: str,
        cls_id: int,
        *,
        suggestions: list[dict[str, object]] | None = None,
    ) -> Path:
        """Save latest unknown object for review while forcing hardware off."""
        self.set_actuation_test_mode(False)
        class_name = str(cls_name or "Unknown object").strip() or "Unknown object"
        with self._state_lock:
            if not self.is_camera_running() or self._latest_frame is None:
                raise RuntimeError("Camera is not running or has no frame yet")
            frame = self._latest_frame.copy()
            detections = list(self._detections)
            cfg = self.cfg.model_copy(deep=True)
        bbox = _unknown_learn_bbox(detections)
        if bbox is None and cfg.roi.enabled and cfg.roi.width > 0 and cfg.roi.height > 0:
            bbox = (
                cfg.roi.x,
                cfg.roi.y,
                cfg.roi.x + cfg.roi.width,
                cfg.roi.y + cfg.roi.height,
            )
        session_id = datetime.now().strftime("unknown_learn_%Y%m%d_%H%M%S_%f")
        return import_manual_camera_frame(
            frame,
            self._queue_dir_for_config(cfg),
            class_name,
            int(cls_id),
            xyxy=bbox,
            catalog_path=self.dataset_file,
            extra_meta={
                "learn_session_id": session_id,
                "learn_mode": "unknown_object",
                "hardware_blocked": True,
                "ai_label_suggestions": suggestions or [],
                "annotation_hint": "Choose the approved class and review this bbox before reference/train.",
                "unknown_labels": ["needs_label_review"] if class_name == "Unknown object" else [],
            },
        )

    def start_capture_session(
        self,
        cls_name: str,
        cls_id: int,
        *,
        target_count: int = 24,
        holdout_count: int = 6,
    ) -> dict[str, object]:
        class_name = str(cls_name or "").strip()
        if not class_name:
            raise ValueError("cls_name is required")
        self.set_actuation_test_mode(False)
        self._capture_session = CaptureSessionManager(
            self._queue_dir_for_config(self.cfg),
            self.dataset_file,
        )
        return self._capture_session.start(
            class_name,
            cls_id,
            target_count=target_count,
            holdout_count=holdout_count,
        )

    def capture_session_status(self) -> dict[str, object]:
        return self._capture_session.status()

    def capture_session_frame(
        self,
        *,
        pose_index: int = 0,
        use_latest_detection_box: bool = True,
    ) -> dict[str, object]:
        with self._state_lock:
            if not self.is_camera_running() or self._latest_frame is None:
                raise RuntimeError("Camera is not running or has no frame yet")
            frame = self._latest_frame.copy()
            detections = list(self._detections)
        bbox = None
        if use_latest_detection_box and detections:
            largest = max(
                detections,
                key=lambda item: max(0, item.bbox[2] - item.bbox[0])
                * max(0, item.bbox[3] - item.bbox[1]),
            )
            bbox = tuple(int(value) for value in largest.bbox)
        if bbox is None and self.cfg.roi.enabled and self.cfg.roi.width > 0 and self.cfg.roi.height > 0:
            bbox = (
                self.cfg.roi.x,
                self.cfg.roi.y,
                self.cfg.roi.x + self.cfg.roi.width,
                self.cfg.roi.y + self.cfg.roi.height,
            )
        return self._capture_session.capture(frame, bbox, pose_index=pose_index)

    def stop_capture_session(self) -> dict[str, object]:
        return self._capture_session.stop()

    def refresh_manual_references(self) -> None:
        with self._state_lock:
            pipeline = self._pipeline
        if pipeline is not None:
            pipeline.refresh_manual_references()

    def live_payload(self) -> dict:
        status = self.status(include_devices=False).model_dump(mode="json")
        with self._state_lock:
            return {
                "status": status,
                "detections": [d.model_dump(mode="json") for d in self._detections],
            }

    def update_bin_fullness(self, bin_index: int, percent: int) -> None:
        if bin_index < 1 or bin_index > BIN_COUNT:
            return
        clamped = max(0, min(100, int(percent)))
        with self._state_lock:
            self._bin_readings[bin_index] = (
                clamped,
                time.monotonic(),
                datetime.now().isoformat(),
            )

    def bin_fullness(self) -> list[BinFullnessDTO]:
        now = time.monotonic()
        with self._state_lock:
            readings = dict(self._bin_readings)
        bins: list[BinFullnessDTO] = []
        for bin_index in range(1, BIN_COUNT + 1):
            reading = readings.get(bin_index)
            label = _bin_label(bin_index)
            if reading is None:
                bins.append(BinFullnessDTO(bin_index=bin_index, label=label))
                continue
            percent, seen_at, updated_at = reading
            bins.append(
                BinFullnessDTO(
                    bin_index=bin_index,
                    label=label,
                    percent=percent,
                    updated_at=updated_at,
                    stale=now - seen_at > BIN_FULLNESS_STALE_AFTER_S,
                )
            )
        return bins

    @staticmethod
    def _queue_dir_for_config(cfg: AppConfig) -> Path:
        output_path = Path(cfg.capture.output_dir).expanduser()
        if output_path.is_absolute():
            return output_path / "low_conf_queue"
        candidate = Path.cwd() / output_path / "low_conf_queue"
        if candidate.exists():
            return candidate
        return resource_path(".") / output_path / "low_conf_queue"

    def _device_snapshot(self) -> tuple[list[dict], list[dict]]:
        now = time.monotonic()
        with self._state_lock:
            if now - self._device_cache_at < self._device_cache_ttl:
                return list(self._cached_usb_cameras), list(self._cached_serial_ports)

        with self._device_scan_lock:
            now = time.monotonic()
            with self._state_lock:
                if now - self._device_cache_at < self._device_cache_ttl:
                    return list(self._cached_usb_cameras), list(self._cached_serial_ports)
            try:
                usb_cameras = [cam for cam in list_pnp_cameras() if cam.get("is_external")]
            except Exception as e:
                logger.warning("agent camera scan failed: {}", e)
                usb_cameras = []
            try:
                serial_ports = list_serial_ports()
            except Exception as e:
                logger.warning("agent serial scan failed: {}", e)
                serial_ports = []
            with self._state_lock:
                self._device_cache_at = time.monotonic()
                self._cached_usb_cameras = list(usb_cameras)
                self._cached_serial_ports = list(serial_ports)
                return list(self._cached_usb_cameras), list(self._cached_serial_ports)

    def close(self) -> None:
        self.stop_camera()
        if self._pipeline is not None:
            self._pipeline.close()
            self._pipeline = None
        if self._uart is not None:
            self._uart.close()
            self._uart = None

    def _camera_loop(self, source: str) -> None:
        cap = None
        try:
            opened = _open_capture(source, self.cfg.camera.width, self.cfg.camera.height)
            if opened is None:
                with self._state_lock:
                    self._camera_connected = False
                    self._camera_message = "Open camera failed"
                    self._camera_diagnostics = {
                        "mode": "direct",
                        "source": source,
                        "usable": False,
                        "black_frame": True,
                        "reason": "open camera failed",
                    }
                return
            cap, backend_name, initial_quality = opened
            with self._state_lock:
                self._camera_connected = True
                self._camera_message = f"Connected {source}"
                self._camera_diagnostics = frame_quality_diagnostics(
                    initial_quality,
                    mode="direct",
                    source=source,
                    backend=backend_name,
                    stale_shared=False,
                )
            read_failures = 0
            while not self._camera_stop.is_set():
                ok, frame = cap.read()
                quality = evaluate_frame_quality(frame if ok else None)
                if not ok or frame is None or not quality.usable:
                    read_failures += 1
                    if read_failures >= 30:
                        reason = "Camera USB black frame" if ok else "Camera USB read failed"
                        with self._state_lock:
                            self._latest_jpeg = _black_jpeg()
                            self._latest_frame = None
                            self._latest_frame_id += 1
                            self._latest_jpeg_frame_id = self._latest_frame_id
                            self._camera_connected = False
                            self._camera_message = reason
                            self._camera_diagnostics = frame_quality_diagnostics(
                                quality,
                                mode="direct",
                                source=source,
                                backend=backend_name,
                                stale_shared=False,
                                reason=reason,
                            )
                            self._camera_message = "Mất tín hiệu camera USB; màn hình giữ màu đen"
                            self._camera_message = reason
                            self._fps = 0.0
                            self._detections = []
                        self._force_actuation_off_for_camera_fault()
                        break
                    time.sleep(0.05)
                    continue
                read_failures = 0
                frame = apply_camera_transform(
                    frame,
                    mirror=self.cfg.camera.mirror,
                    rotation=self.cfg.camera.rotation,
                )
                self._shared_publisher.publish(frame)
                now = time.time()
                if self._last_frame_at:
                    inst_fps = 1.0 / max(now - self._last_frame_at, 1e-6)
                    self._fps = 0.9 * self._fps + 0.1 * inst_fps
                self._last_frame_at = now
                with self._state_lock:
                    self._latest_frame = frame.copy()
                    self._latest_frame_id += 1
                    self._camera_diagnostics = frame_quality_diagnostics(
                        quality,
                        mode="direct",
                        source=source,
                        backend=backend_name,
                        stale_shared=False,
                    )
        except Exception as e:
            logger.warning("agent camera loop failed: {}", e)
            with self._state_lock:
                self._camera_connected = False
                self._camera_message = f"Camera loop failed: {e}"
                self._fps = 0.0
                self._detections = []
        finally:
            self._camera_stop.set()
            if cap is not None:
                cap.release()
            with self._state_lock:
                self._camera_connected = False
                if self._camera_message.startswith("Connected "):
                    self._camera_message = "Camera stopped"
            self._release_camera_lock()

    def _shared_camera_loop(self) -> None:
        missing_reads = 0
        try:
            while not self._camera_stop.is_set():
                shared = read_shared_frame()
                if shared is None:
                    missing_reads += 1
                    shared_diag = shared_frame_diagnostics()
                    with self._state_lock:
                        self._camera_connected = False
                        self._camera_message = "Waiting for shared camera stream"
                        self._camera_diagnostics = {
                            "mode": "shared",
                            "source": "shared-camera",
                            "usable": False,
                            "black_frame": True,
                            "stale_shared": bool(shared_diag.get("stale", True)),
                            "reason": str(shared_diag.get("reason") or "waiting for shared camera stream"),
                            "shared": shared_diag,
                        }
                        if missing_reads >= 20:
                            self._latest_jpeg = _black_jpeg()
                            self._latest_frame = None
                            self._latest_frame_id += 1
                            self._latest_jpeg_frame_id = self._latest_frame_id
                            self._fps = 0.0
                            self._detections = []
                    self._force_actuation_off_for_camera_fault()
                    time.sleep(0.1)
                    continue

                missing_reads = 0
                now = time.time()
                if self._last_frame_at:
                    inst_fps = 1.0 / max(now - self._last_frame_at, 1e-6)
                    self._fps = 0.9 * self._fps + 0.1 * inst_fps
                self._last_frame_at = now
                with self._state_lock:
                    self._latest_frame = shared.frame.copy()
                    self._latest_frame_id += 1
                    self._latest_jpeg = shared.jpeg
                    self._latest_jpeg_frame_id = self._latest_frame_id
                    self._camera_connected = True
                    self._camera_message = "Connected via shared camera stream"
                    self._camera_diagnostics = frame_quality_diagnostics(
                        shared.quality,
                        mode="shared",
                        source="shared-camera",
                        stale_shared=False,
                        shared_age_s=round(shared.age_s, 2),
                    )
                time.sleep(STREAM_FRAME_INTERVAL_S)
        finally:
            with self._state_lock:
                self._camera_connected = False

    def _inference_loop(self) -> None:
        while not self._camera_stop.is_set():
            with self._state_lock:
                frame = None if self._latest_frame is None else self._latest_frame.copy()
            if frame is None:
                time.sleep(0.03)
                continue
            started = time.perf_counter()
            detections = self._process_frame(frame)
            latency_ms = (time.perf_counter() - started) * 1000.0
            with self._state_lock:
                self._latency_ms = latency_ms
                self._detections = detections
            elapsed = time.perf_counter() - started
            time.sleep(max(0.01, STREAM_INFERENCE_INTERVAL_S - elapsed))

    def _process_frame(self, frame: np.ndarray) -> list[DetectionDTO]:
        if not self._ensure_pipeline():
            return []
        assert self._pipeline is not None
        ts = datetime.now()
        try:
            detections = self._pipeline.process_frame(frame, ts)
        except Exception as e:
            self._model_message = f"Inference failed: {e}"
            logger.warning("agent inference failed: {}", e)
            return []
        return [
            self._detection_dto(d, ts)
            for d in detections
        ]

    def _detection_dto(self, detection, ts: datetime) -> DetectionDTO:
        mapping = next(
            (m for m in self.cfg.mappings if m.enabled and m.class_name == detection.cls_name),
            None,
        )
        fallback = self.cfg.unknown_fallback
        if mapping is None and detection.cls_name == fallback.class_name:
            mapping = ClassMapping(
                class_name=fallback.class_name,
                command=fallback.command,
                bin_index=fallback.bin_index,
                enabled=True,
            )
        three_bin_command = parse_three_bin_class_name(detection.cls_name)
        command = None
        route_label = None
        bin_index = None
        serial_payload = None
        ack = None
        if three_bin_command is not None:
            category = category_for_command(three_bin_command)
            if category is not None:
                command = category.code
                route_label = category.name
                bin_index = category.bin_index
        elif mapping is not None:
            mapping = normalize_mapping_to_three_bins(mapping)
            category = category_for_command(mapping.command)
            if category is not None:
                command = category.code
                route_label = category.name
                bin_index = category.bin_index
            else:
                command = mapping.command.strip().upper()
                bin_index = int(mapping.bin_index)
        if command:
            try:
                serial_payload = encode_sort(
                    command,
                    detection.conf,
                    protocol=self.cfg.uart.protocol,
                ).decode("utf-8").rstrip("\n")
            except ValueError:
                serial_payload = None
            guard_status = ""
            if self._pipeline is not None:
                guard_status = str(getattr(self._pipeline, "dispatch_status", "") or "")
            ack = (
                guard_status
                or ("pending" if self._uart is not None and self._uart.connected else "uart_off")
            )
        return DetectionDTO(
            cls_id=detection.cls_id,
            cls_name=detection.cls_name,
            confidence=detection.conf,
            bbox=detection.xyxy,
            timestamp=ts.isoformat(),
            uart_command=command,
            route_label=route_label,
            bin_index=bin_index,
            serial_payload=serial_payload,
            ack=ack,
            source=str(getattr(detection, "source", "YOLO") or "YOLO"),
        )

    def _ensure_pipeline(self) -> bool:
        if self._pipeline is not None:
            return True
        try:
            self._engine = InferenceEngine(
                self.cfg.model.path,
                device=self.cfg.model.device,
                conf=self.cfg.model.conf_threshold,
                iou=self.cfg.model.iou_threshold,
                imgsz=self.cfg.model.input_size,
                half=self.cfg.model.half_precision,
            )
            self._pipeline = Pipeline(
                self.cfg,
                self._engine,
                self._uart,
                self.history_file,
                speaker=self._speaker,
            )
            with self._state_lock:
                actuation_enabled = self._actuation_test_enabled
            self._pipeline.set_hardware_dispatch_enabled(actuation_enabled)
            self._pipeline.on_capture_saved = lambda _path: None
            self._model_message = (
                f"Loaded {len(self._engine.class_names)} classes on {self._engine.device_label}"
            )
            return True
        except Exception as e:
            self._model_message = str(e)
            logger.warning("agent model load failed: {}", e)
            return False

    def _reset_pipeline_locked(self) -> None:
        if self._pipeline is not None:
            self._pipeline.close()
        self._pipeline = None
        self._engine = None
        self._detections = []
        self._latency_ms = 0.0
        self._model_message = "Model config changed; waiting for next frame"

    def _restart_uart_from_config(self) -> None:
        if self._uart is not None:
            self._uart.close()
            self._uart = None
        if not self.cfg.uart.port.strip():
            self._auto_select_uart_if_blank()
        port = self.cfg.uart.port.strip()
        if not self._is_usb_uart_port(port):
            present, eligible = self._uart_port_presence(port)
            if port and present and not eligible:
                self.cfg.uart.port = ""
                save_config(self.cfg, self.config_file)
                self._auto_select_uart_if_blank()
                port = self.cfg.uart.port.strip()
            else:
                self._uart_warning = (
                    f"UART OFF, khong gui xuong phan cung: {port or 'configured port'} not visible."
                )
                if self._pipeline is not None:
                    self._pipeline.set_uart(None)
                return
        if not port:
            if self._pipeline is not None:
                self._pipeline.set_uart(None)
            return
        sender = ThreadUartSender(
            port=port,
            baud=self.cfg.uart.baud,
            ack_timeout_ms=self.cfg.uart.ack_timeout_ms,
            on_ack=self._on_uart_ack,
            on_bin=self.update_bin_fullness,
            protocol=self.cfg.uart.protocol,
        )
        sender.open()
        self._uart = sender
        if self._pipeline is not None:
            self._pipeline.set_uart(sender if sender.connected else None)

    def _auto_select_uart_if_blank(self) -> None:
        if self.cfg.uart.port.strip():
            return
        result = select_single_usb_serial_port(list_serial_ports())
        self._uart_warning = result.message
        if not result.selected:
            return
        self.cfg.uart.port = result.port
        save_config(self.cfg, self.config_file)
        logger.info("agent auto-selected uart port={}", result.port)

    def _on_uart_ack(self, track_id: int, command: str, status: str, rtt_ms: int) -> None:
        if self._pipeline is not None:
            self._pipeline.on_ack(track_id, command, status, rtt_ms)

    def _sanitize_config(self, cfg: AppConfig) -> AppConfig:
        clean = normalize_speaker_output_config(cfg)
        clean.camera.source = ""
        port = clean.uart.port.strip()
        _present, eligible = self._uart_port_presence(port)
        clean.uart.port = port if eligible else ""
        return clean

    @staticmethod
    def _is_usb_uart_port(port: str) -> bool:
        if not port:
            return False
        wanted = port.strip().upper()
        return any(
            str(p.get("device", "")).strip().upper() == wanted and is_eligible_usb_serial_port(p)
            for p in list_serial_ports()
        )

    @staticmethod
    def _uart_port_presence(port: str) -> tuple[bool, bool]:
        if not port:
            return False, False
        wanted = port.strip().upper()
        for candidate in list_serial_ports():
            if str(candidate.get("device", "")).strip().upper() != wanted:
                continue
            return True, is_eligible_usb_serial_port(candidate)
        return False, False

    def _release_camera_lock(self) -> None:
        if self._camera_lock is not None:
            self._camera_lock.release()
            self._camera_lock = None


def _unknown_learn_bbox(detections: list[DetectionDTO]) -> tuple[int, int, int, int] | None:
    if not detections:
        return None
    unknown = [d for d in detections if d.cls_name.casefold() == "unknown object"]
    pool = unknown or detections
    best = max(pool, key=lambda item: _bbox_area(item.bbox))
    if _bbox_area(best.bbox) <= 0:
        return None
    return tuple(int(value) for value in best.bbox)


def _bbox_area(bbox: tuple[int, int, int, int]) -> int:
    return max(0, int(bbox[2]) - int(bbox[0])) * max(0, int(bbox[3]) - int(bbox[1]))


def _open_capture(source: str, width: int, height: int) -> tuple[Any, str, FrameQuality] | None:
    import cv2

    src_raw = normalize_camera_source(source)
    is_index = src_raw.isdigit()
    src: int | str = int(src_raw) if is_index else src_raw
    attempts = [("ANY", cv2.CAP_ANY)]
    if is_index:
        attempts = [
            ("DSHOW", cv2.CAP_DSHOW),
            ("MSMF", cv2.CAP_MSMF),
            ("ANY", cv2.CAP_ANY),
        ]
        hint = backend_hint(source)
        if hint:
            attempts = [item for item in attempts if item[0] == hint]
    for name, backend in attempts:
        cap = cv2.VideoCapture(src, backend) if is_index else cv2.VideoCapture(src)
        if not cap.isOpened():
            cap.release()
            continue
        if is_index:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        quality = _capture_best_quality(cap)
        if quality.usable:
            return cap, name, quality
        logger.warning(
            "agent camera source={} backend={} rejected frame: {}",
            source,
            name,
            quality.reason,
        )
        cap.release()
    return None


def _capture_best_quality(cap, *, frames: int = 5) -> FrameQuality:
    qualities: list[FrameQuality] = []
    for _ in range(max(1, frames)):
        ok, frame = cap.read()
        if ok and frame is not None:
            qualities.append(evaluate_frame_quality(frame))
        time.sleep(0.03)
    if not qualities:
        return FrameQuality(reason="no frame")
    return max(
        qualities,
        key=lambda item: (
            item.usable,
            item.non_black_ratio,
            item.mean_brightness,
            item.variance,
        ),
    )


def _camera_probe_failure_reason(
    probes: list[dict[str, object]], shared_diag: dict[str, object]
) -> str:
    if probes:
        reasons = [
            str(item.get("reason") or "unknown")
            for item in probes
            if str(item.get("reason") or "").strip()
        ]
        if any("black" in reason.lower() for reason in reasons):
            return "USB Camera detected but frame is black"
        return f"USB Camera detected but no usable frame: {', '.join(reasons[:3])}"
    if bool(shared_diag.get("exists")):
        return f"No usable USB Camera frame; shared camera {shared_diag.get('reason')}"
    return "No usable USB Camera detected"


def _encode_jpeg(frame: np.ndarray, *, max_width: int | None = None) -> bytes:
    import cv2

    if max_width is not None and frame.shape[1] > max_width:
        scale = max_width / frame.shape[1]
        height = max(1, int(frame.shape[0] * scale))
        frame = cv2.resize(frame, (max_width, height), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    if not ok:
        return _black_jpeg()
    return buf.tobytes()


def _black_jpeg() -> bytes:
    import cv2

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        return b""
    return buf.tobytes()


def _bin_label(bin_index: int) -> str:
    category = category_for_bin_index(bin_index)
    if category is not None:
        return category.name
    return f"Thung {bin_index}"


def _age_seconds(now: float, then: float | None) -> float | None:
    if then is None:
        return None
    return round(max(0.0, now - then), 2)


__all__ = ["AgentRuntime", "ThreadUartSender"]
