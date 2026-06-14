from app.core.detection_filtering import suppress_overlapping_detections
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
