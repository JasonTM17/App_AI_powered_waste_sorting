import os
import time

import pytest
from PySide6.QtCore import QCoreApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.uart import UartWorker


class FakeSerial:
    def __init__(self, port, baud, timeout=0.1):
        self.port = port
        self.baud = baud
        self.is_open = True
        self._tx = []
        self._rx = []

    def write(self, data):
        self._tx.append(bytes(data))
        if data.startswith(b"SORT:"):
            cmd = data.decode().split(":")[1]
            self._rx.append(f"ACK:{cmd}\n".encode())
        if data == b"PING\n":
            self._rx.append(b"PONG\n")
        return len(data)

    def readline(self):
        if self._rx:
            return self._rx.pop(0)
        return b""

    def close(self):
        self.is_open = False


@pytest.fixture
def fake_serial(monkeypatch):
    instances = []
    def factory(port, baud, timeout=0.1):
        s = FakeSerial(port, baud, timeout)
        instances.append(s)
        return s
    monkeypatch.setattr("app.core.uart.serial.Serial", factory)
    return instances


def _wait(cond, timeout=2.0):
    deadline = time.time() + timeout
    while not cond() and time.time() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.02)


def test_send_receives_ack(fake_serial, qtbot):
    acks = []
    w = UartWorker(port="COM_FAKE", baud=9600, ack_timeout_ms=500)
    w.ack_received.connect(lambda track_id, cmd, status, rtt: acks.append((track_id, cmd, status)))
    w.start()
    _wait(lambda: w.is_connected, 2.0)
    w.send(track_id=1, command="S", conf=0.9)
    _wait(lambda: len(acks) >= 1, 2.0)
    w.stop(); w.wait(2000)
    assert acks and acks[0] == (1, "S", "ok")


def test_no_ack_marked_when_silent(monkeypatch, qtbot):
    class SilentSerial(FakeSerial):
        def write(self, data):
            self._tx.append(bytes(data))
            return len(data)
    monkeypatch.setattr("app.core.uart.serial.Serial", lambda p, b, timeout=0.1: SilentSerial(p, b, timeout))
    acks = []
    w = UartWorker(port="COM_FAKE", baud=9600, ack_timeout_ms=200)
    w.ack_received.connect(lambda tid, c, st, rtt: acks.append((tid, c, st)))
    w.start()
    _wait(lambda: w.is_connected, 2.0)
    w.send(track_id=2, command="P", conf=0.8)
    _wait(lambda: len(acks) >= 1, 2.0)
    w.stop(); w.wait(2000)
    assert acks and acks[0] == (2, "P", "no_ack")
