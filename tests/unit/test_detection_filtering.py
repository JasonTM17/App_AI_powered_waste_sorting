import numpy as np

from app.core.detection_filtering import (
    find_ambiguous_organic_candidate,
    is_uniform_empty_tray_artifact,
    suppress_overlapping_detections,
)
from app.core.events import Detection


def test_suppress_overlapping_detections_keeps_strongest_label():
    detections = [
        Detection(0, "Aluminum can", 0.62, (20, 20, 220, 220)),
        Detection(1, "Plastic bottle", 0.16, (22, 21, 219, 222)),
    ]

    filtered = suppress_overlapping_detections(detections)

    assert [(item.cls_name, item.conf) for item in filtered] == [("Aluminum can", 0.62)]


def test_suppress_overlapping_detections_keeps_separate_objects():
    detections = [
        Detection(0, "Aluminum can", 0.62, (20, 20, 100, 100)),
        Detection(1, "Plastic bottle", 0.55, (160, 20, 260, 120)),
    ]

    filtered = suppress_overlapping_detections(detections)

    assert [item.cls_name for item in filtered] == ["Aluminum can", "Plastic bottle"]


def test_suppress_overlapping_detections_handles_large_container_box():
    detections = [
        Detection(0, "Aluminum can", 0.53, (202, 95, 515, 478)),
        Detection(1, "Plastic bottle", 0.14, (158, 11, 640, 478)),
    ]

    filtered = suppress_overlapping_detections(detections)

    assert [item.cls_name for item in filtered] == ["Aluminum can"]


def test_uniform_empty_tray_rejects_full_frame_false_positive():
    frame = np.full((240, 320, 3), 175, dtype=np.uint8)
    detections = [Detection(18, "Paper", 0.54, (2, 2, 318, 238))]

    assert is_uniform_empty_tray_artifact(frame, detections)


def test_uniform_empty_tray_keeps_colored_bagasse_material():
    frame = np.full((240, 320, 3), 175, dtype=np.uint8)
    frame[70:180, 50:270] = (95, 145, 185)
    detections = [Detection(19, "Paper bag", 0.17, (2, 2, 318, 238))]

    assert not is_uniform_empty_tray_artifact(frame, detections)


def test_ambiguous_paper_and_organic_candidate_requires_close_scores():
    close = [
        Detection(19, "Paper bag", 0.17, (10, 10, 300, 220)),
        Detection(17, "Organic", 0.16, (12, 11, 299, 219)),
    ]
    far = [
        Detection(19, "Paper bag", 0.65, (10, 10, 300, 220)),
        Detection(17, "Organic", 0.08, (12, 11, 299, 219)),
    ]

    assert find_ambiguous_organic_candidate(close, max_primary_confidence=0.7)
    assert find_ambiguous_organic_candidate(far, max_primary_confidence=0.7) is None
