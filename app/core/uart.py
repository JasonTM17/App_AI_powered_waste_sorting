"""UART worker: send commands, parse responses, auto-reconnect."""

from __future__ import annotations

import queue
import time
from contextlib import suppress
from dataclasses import dataclass

import serial
from PySide6.QtCore import QThread, Signal

from app.core.uart_protocol import (
    UartProtocol,
    encode_ping,
    encode_profile_request,
    encode_sort,
    expected_ack_command,
    parse_line,
    protocol_expects_ack,
)
from app.utils.logging import logger

ARDUINO_SERIAL_RESET_SETTLE_S = 2.2


@dataclass
class _Cmd:
    track_id: int
    command: str
    conf: float
    enqueued_at: float


class UartWorker(QThread):
    ack_received = Signal(int, str, str, object)
    connected = Signal(bool)
    error = Signal(str)

    def __init__(
        self,
        port="",
        baud=9600,
        ack_timeout_ms=200,
        auto_reconnect=True,
        protocol: UartProtocol = "sort_line",
    ):
        super().__init__()
        self._port = port
        self._baud = baud
        self._ack_timeout = ack_timeout_ms / 1000.0
        self._auto_reconnect = auto_reconnect
        self._protocol = protocol
        self._expects_ack = protocol_expects_ack(protocol)
        self._stop = False
        self._queue: queue.Queue[_Cmd] = queue.Queue(maxsize=100)
        self._ser: serial.Serial | None = None
        self.is_connected = False
        self._last_open_warn = 0.0

    def send(self, track_id, command, conf):
        try:
            self._queue.put_nowait(_Cmd(track_id, command, conf, time.time()))
        except queue.Full:
            with suppress(queue.Empty):
                self._queue.get_nowait()
            self._queue.put_nowait(_Cmd(track_id, command, conf, time.time()))

    def _open(self):
        try:
            self._ser = serial.Serial(self._port, self._baud, timeout=0.1)
            self.is_connected = True
            self.connected.emit(True)
            if self._expects_ack:
                time.sleep(ARDUINO_SERIAL_RESET_SETTLE_S)
                self._ser.write(encode_ping())
                self._ser.write(encode_profile_request())
            logger.info("uart connected port={} protocol={}", self._port, self._protocol)
            self._last_open_warn = 0.0
            return True
        except Exception as e:
            now = time.time()
            # throttle the noisy 'open failed' line to once every 30s so
            # logs are still informative but not flooded while user has
            # nothing on COM3
            if now - self._last_open_warn > 30.0:
                logger.warning("uart open failed port={} err={}", self._port, e)
                self._last_open_warn = now
            self.is_connected = False
            self.connected.emit(False)
            self.error.emit(f"open {self._port} failed: {e}")
            return False

    def _read_until_ack(self, expected_cmd, deadline):
        if self._ser is None:
            return None
        while time.time() < deadline:
            try:
                raw = self._ser.readline()
            except Exception:
                return None
            if not raw:
                continue
            parsed = parse_line(raw)
            if parsed is None:
                continue
            kind, cmd, payload = parsed
            if kind == "ack" and cmd == expected_cmd:
                return ("ok", None)
            if kind == "nack" and cmd == expected_cmd:
                return ("error", payload)
            if kind == "log":
                logger.info("uart log: {}", payload)
            if kind == "profile":
                logger.info("uart profile: {}", cmd)
            if kind == "proximity":
                logger.info("uart proximity: {}", cmd)
        return None

    def run(self):
        while not self._stop:
            if (self._ser is None or not self.is_connected) and not self._open():
                if not self._auto_reconnect:
                    time.sleep(0.5)
                    continue
                time.sleep(2.0)
                continue
            try:
                cmd = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            payload = encode_sort(cmd.command, cmd.conf, protocol=self._protocol)
            t0 = time.time()
            try:
                if self._ser is None:
                    self._close()
                    continue
                self._ser.write(payload)
            except Exception as e:
                logger.warning("uart write failed: {}", e)
                self._close()
                continue
            rtt = int((time.time() - t0) * 1000)
            if not self._expects_ack:
                self.ack_received.emit(cmd.track_id, cmd.command, "ok", rtt)
                continue
            expected_ack = expected_ack_command(cmd.command, self._protocol)
            deadline = t0 + self._ack_timeout
            outcome = self._read_until_ack(expected_ack, deadline)
            rtt = int((time.time() - t0) * 1000)
            if outcome is None:
                self.ack_received.emit(cmd.track_id, cmd.command, "no_ack", rtt)
            else:
                status, _ = outcome
                self.ack_received.emit(cmd.track_id, cmd.command, status, rtt)
        self._close()

    def _close(self):
        if self._ser is not None:
            with suppress(Exception):
                self._ser.close()
        self._ser = None
        self.is_connected = False
        self.connected.emit(False)

    def stop(self):
        self._stop = True
