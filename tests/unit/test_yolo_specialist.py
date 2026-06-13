from typing import ClassVar

from app.core.config import SpecialistModelConfig
from app.core.events import Detection
from app.core.inference import (
    YOLO_SPECIALIST_SOURCE,
    InferenceEngine,
    merge_specialist_detections,
)


def _detection(
    cls_id: int,
    cls_name: str,
    conf: float,
    xyxy: tuple[int, int, int, int],
    *,
    source: str = "YOLO",
) -> Detection:
    return Detection(cls_id, cls_name, conf, xyxy, source=source)


def test_specialist_does_not_override_confident_primary_detection():
    primary = [_detection(3, "Cardboard", 0.8, (10, 10, 100, 100))]
    specialist = [
        _detection(
            42,
            "Pen",
            0.6,
            (12, 12, 98, 98),
            source=YOLO_SPECIALIST_SOURCE,
        )
    ]

    merged = merge_specialist_detections(
        primary,
        specialist,
        primary_conf_threshold=0.4,
        overlap_iou=0.5,
    )

    assert merged == primary


def test_specialist_replaces_low_confidence_gap_without_removing_raw_primary():
    primary = [_detection(3, "Cardboard", 0.2, (10, 10, 100, 100))]
    specialist_detection = _detection(
        42,
        "Pen",
        0.3,
        (12, 12, 98, 98),
        source=YOLO_SPECIALIST_SOURCE,
    )

    merged = merge_specialist_detections(
        primary,
        [specialist_detection],
        primary_conf_threshold=0.4,
        overlap_iou=0.5,
    )

    assert merged == [*primary, specialist_detection]


def test_specialist_suppresses_overlapping_duplicate_classes():
    stronger = _detection(
        42,
        "Pen",
        0.5,
        (10, 10, 100, 100),
        source=YOLO_SPECIALIST_SOURCE,
    )
    weaker = _detection(
        44,
        "Toothbrush",
        0.3,
        (12, 12, 98, 98),
        source=YOLO_SPECIALIST_SOURCE,
    )

    merged = merge_specialist_detections(
        [],
        [weaker, stronger],
        primary_conf_threshold=0.4,
        overlap_iou=0.5,
    )

    assert merged == [stronger]


def test_specialist_load_keeps_primary_class_names_isolated(tmp_path):
    model_path = tmp_path / "specialist.pt"
    model_path.write_bytes(b"stub")

    class FakeYolo:
        names: ClassVar[dict[int, str]] = {0: "Pen", 1: "Battery"}

        def __init__(self, _path: str) -> None:
            pass

    engine = InferenceEngine.__new__(InferenceEngine)
    engine.class_names = {0: "Aerosols", 1: "Aluminum can"}
    engine._specialist_model = None
    engine._specialist_class_names = {}
    engine._specialist_class_ids = []
    engine._specialist_thresholds = {}
    engine._specialist_nms_iou = 0.7
    engine._specialist_overlap_iou = 0.5

    engine._load_specialist(
        SpecialistModelConfig(
            enabled=True,
            path=str(model_path),
            class_thresholds={"Pen": 0.2, "Battery": 0.3},
        ),
        FakeYolo,
    )

    assert engine.class_names == {0: "Aerosols", 1: "Aluminum can"}
    assert engine._specialist_class_names == {0: "Pen", 1: "Battery"}
    assert engine._specialist_class_ids == [0, 1]
