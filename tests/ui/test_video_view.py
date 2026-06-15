import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.events import Detection
from app.ui.widgets.video_view import VideoView


def test_video_view_accepts_frame_and_detections(qtbot):
    v = VideoView()
    qtbot.addWidget(v)
    frame = np.full((240, 320, 3), 128, dtype=np.uint8)
    v.set_frame(frame)
    v.set_detections([Detection(0, "paper", 0.9, (10, 10, 100, 100))])
    assert v._pixmap is not None
    assert v._frame_w == 320 and v._frame_h == 240
    assert len(v._detections) == 1


def test_video_view_keeps_camera_aspect_ratio(qtbot):
    v = VideoView()
    qtbot.addWidget(v)
    v.resize(900, 400)
    v.set_frame(np.zeros((480, 640, 3), dtype=np.uint8))

    scaled = v._ensure_scaled()

    assert scaled is not None
    assert scaled.width() == 533
    assert scaled.height() == 400
