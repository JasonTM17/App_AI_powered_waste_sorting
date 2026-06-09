import numpy as np

from app.utils.camera_frame_quality import evaluate_frame_quality


def test_frame_quality_rejects_black_frame():
    quality = evaluate_frame_quality(np.zeros((24, 32, 3), dtype=np.uint8))

    assert quality.usable is False
    assert quality.reason == "black frame"
    assert quality.non_black_ratio == 0


def test_frame_quality_accepts_non_black_frame():
    frame = np.zeros((24, 32, 3), dtype=np.uint8)
    frame[:, :, 1] = 160

    quality = evaluate_frame_quality(frame)

    assert quality.usable is True
    assert quality.mean_brightness > 2
    assert quality.non_black_ratio > 0.9
