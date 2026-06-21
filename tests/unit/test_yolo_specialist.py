from typing import ClassVar

import app.core.inference as inference_module
from app.core.config import SpecialistModelConfig
from app.core.events import Detection
from app.core.inference import (
    YOLO_SPECIALIST_SOURCE,
    InferenceEngine,
    merge_specialist_detections,
    specialist_shape_allowed,
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


def test_specialist_rejects_pen_label_for_wall_charger_shape():
    charger_as_pen = _detection(
        42,
        "Pen",
        0.61,
        (84, 109, 582, 419),
        source=YOLO_SPECIALIST_SOURCE,
    )

    assert specialist_shape_allowed(charger_as_pen, {"Pen": 2.2}) is False


def test_specialist_keeps_elongated_pen_shape():
    pen = _detection(
        42,
        "Pen",
        0.61,
        (40, 100, 560, 180),
        source=YOLO_SPECIALIST_SOURCE,
    )

    assert specialist_shape_allowed(pen, {"Pen": 2.2}) is True


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
    engine._specialist_min_aspect_ratios = {}
    engine._specialist_routes = {}
    engine._specialist_output_thresholds = {}
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


def test_specialist_route_maps_wall_charger_to_electronics_operator_label():
    engine = InferenceEngine.__new__(InferenceEngine)
    engine._specialist_routes = {"Wall charger": ("Electronics", "Cục sạc")}

    mapped = engine._map_specialist_detection(
        Detection(
            6,
            "Wall charger",
            0.81,
            (10, 20, 100, 120),
            source=YOLO_SPECIALIST_SOURCE,
        )
    )

    assert mapped.cls_name == "Electronics"
    assert mapped.operator_label == "Cục sạc"
    assert mapped.cls_id == 9


def test_specialist_runs_only_when_primary_is_uncertain():
    engine = InferenceEngine.__new__(InferenceEngine)
    engine.conf = 0.4

    assert engine._should_run_specialist([]) is True
    assert engine._should_run_specialist([Detection(3, "Cardboard", 0.20, (0, 0, 10, 10))]) is True
    assert engine._should_run_specialist([Detection(3, "Cardboard", 0.80, (0, 0, 10, 10))]) is False


def test_model_path_falls_back_to_project_data_for_desktop_shortcut(tmp_path, monkeypatch):
    model_path = tmp_path / "models" / "real-camera.pt"
    model_path.parent.mkdir()
    model_path.write_bytes(b"stub")

    monkeypatch.setattr(inference_module, "resource_path", lambda _path: tmp_path / "bundle-missing")
    monkeypatch.setattr(inference_module, "resolve_data_path", lambda _path: model_path)

    assert inference_module._resolve_model_path("models/real-camera.pt") == model_path
