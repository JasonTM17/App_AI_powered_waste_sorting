"""UART worker: send commands, parse responses, auto-reconnect."""
from __future__ import annotations

import queue
import time
from dataclasses import dataclass

import serial
from PySide6.QtCore import QThread, Signal

from app.core.uart_protocol import encode_ping, encode_sort, parse_line
from app.utils.logging import logger


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

    def __init__(self, port="COM3", baud=9600, ack_timeout_ms=200, auto_reconnect=True):
        super().__init__()
        self._port = port
        self._baud = baud
        self._ack_timeout = ack_timeout_ms / 1000.0
        self._auto_reconnect = auto_reconnect
        self._stop = False
        self._queue: queue.Queue[_Cmd] = queue.Queue(maxsize=100)
        self._ser = None
        self.is_connected = False

    def send(self, track_id, command, conf):
        try:
            self._queue.put_nowait(_Cmd(track_id, command, conf, time.time()))
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self._queue.put_nowait(_Cmd(track_id, command, conf, time.time()))

    def _open(self):
        try:
            self._ser = serial.Serial(self._port, self._baud, timeout=0.1)
            self.is_connected = True
            self.connected.emit(True)
            self._ser.write(encode_ping())
            return True
        except Exception as e:
            logger.warning("uart open failed port={} err={}", self._port, e)
            self.is_connected = False
            self.connected.emit(False)
            self.error.emit(f"open {self._port} failed: {e}")
            return False

    def _read_until_ack(self, expected_cmd, deadline):
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
        return None

    def run(self):
        while not self._stop:
            if self._ser is None or not self.is_connected:
                if not self._open():
                    if not self._auto_reconnect:
                        time.sleep(0.5)
                        continue
                    time.sleep(2.0)
                    continue
            try:
                cmd = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            payload = encode_sort(cmd.command, cmd.conf)
            t0 = time.time()
            try:
                self._ser.write(payload)
            except Exception as e:
                logger.warning("uart write failed: {}", e)
                self._close()
                continue
            deadline = t0 + self._ack_timeout
            outcome = self._read_until_ack(cmd.command, deadline)
            rtt = int((time.time() - t0) * 1000)
            if outcome is None:
                self.ack_received.emit(cmd.track_id, cmd.command, "no_ack", rtt)
            else:
                status, _ = outcome
                self.ack_received.emit(cmd.track_id, cmd.command, status, rtt)
        self._close()

    def _close(self):
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None
        self.is_connected = False
        self.connected.emit(False)

    def stop(self):
        self._stop = True
