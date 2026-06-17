import os
import time

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.camera import (
    CAMERA_FRAME_INTERVAL_S,
    CameraWorker,
    _sleep_remaining_frame_interval,
)


@pytest.fixture
def fake_video(tmp_path):
    out = tmp_path / "fake.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out), fourcc, 10, (320, 240))
    for i in range(20):
        frame = np.full((240, 320, 3), i * 10, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return out


def test_camera_emits_frames(fake_video, qtbot):
    received = []
    worker = CameraWorker(source=str(fake_video), width=320, height=240)
    worker.frame_ready.connect(lambda f: received.append(f))
    worker.start()
    deadline = time.time() + 3
    while len(received) < 3 and time.time() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.05)
    worker.stop()
    worker.wait(2000)
    assert len(received) >= 3


def test_camera_emits_error_on_bad_source(qtbot):
    errors = []
    worker = CameraWorker(source="nonexistent_file.mp4")
    worker.error.connect(lambda msg: errors.append(msg))
    worker.start()
    deadline = time.time() + 5
    while not errors and time.time() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.1)
    worker.stop()
    worker.wait(2000)
    assert errors


def test_camera_frame_interval_helper_sleeps_only_remaining_time():
    slept: list[float] = []

    remaining = _sleep_remaining_frame_interval(
        10.0,
        now=10.01,
        sleep_fn=slept.append,
    )

    assert remaining == pytest.approx(CAMERA_FRAME_INTERVAL_S - 0.01)
    assert slept == [remaining]
    assert _sleep_remaining_frame_interval(10.0, now=11.0, sleep_fn=slept.append) == 0.0
