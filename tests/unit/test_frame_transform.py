import numpy as np

from app.core.frame_transform import apply_camera_transform


def test_apply_camera_transform_keeps_baseline_orientation():
    frame = np.zeros((2, 3, 3), dtype=np.uint8)
    frame[0, 0] = [10, 0, 0]

    out = apply_camera_transform(frame, mirror=False, rotation=0)

    assert out.shape == (2, 3, 3)
    assert out[0, 0, 0] == 10


def test_apply_camera_transform_rotates_90_clockwise():
    frame = np.zeros((2, 3, 3), dtype=np.uint8)
    frame[0, 0] = [10, 0, 0]

    out = apply_camera_transform(frame, rotation=90)

    assert out.shape == (3, 2, 3)
    assert out[0, 1, 0] == 10


def test_apply_camera_transform_mirrors_before_rotation():
    frame = np.zeros((2, 3, 3), dtype=np.uint8)
    frame[0, 0] = [10, 0, 0]

    out = apply_camera_transform(frame, mirror=True, rotation=0)

    assert out[0, 2, 0] == 10
