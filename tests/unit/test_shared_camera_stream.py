import os
import time

import numpy as np

from app.utils import shared_camera_stream


def test_shared_frame_publisher_round_trips_frame(monkeypatch, tmp_path):
    monkeypatch.setattr(shared_camera_stream, "app_data_dir", lambda: tmp_path)
    publisher = shared_camera_stream.SharedFramePublisher(min_interval_s=0, max_width=8)
    frame = np.zeros((12, 16, 3), dtype=np.uint8)
    frame[:, :, 1] = 200

    publisher.publish(frame)

    shared = shared_camera_stream.read_shared_frame(stale_after_s=10)

    assert shared is not None
    assert shared.jpeg
    assert shared.frame.shape[1] == 8
    assert shared.age_s >= 0


def test_read_shared_frame_ignores_stale_file(monkeypatch, tmp_path):
    monkeypatch.setattr(shared_camera_stream, "app_data_dir", lambda: tmp_path)
    publisher = shared_camera_stream.SharedFramePublisher(min_interval_s=0)
    frame = np.zeros((8, 8, 3), dtype=np.uint8)

    publisher.publish(frame)
    path = shared_camera_stream.shared_frame_path()
    stale_time = time.time() - 5
    os.utime(path, (stale_time, stale_time))

    assert shared_camera_stream.read_shared_frame(stale_after_s=1) is None
