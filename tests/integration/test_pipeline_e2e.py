import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import cv2
import numpy as np
from PIL import Image

from app.core.config import MULTI_CLASS_WARNING_TEXT, AppConfig, ClassMapping
from app.core.events import Detection
from app.core.inference import YOLO_SPECIALIST_SOURCE
from app.core.pipeline import Pipeline
from app.core.three_bin_classifier import (
    THREE_BIN_SOURCE,
    ThreeBinPrediction,
    three_bin_display_name,
)
from app.core.waste_categories import category_for_command


class _StubInfer:
    class_names: ClassVar[dict[int, str]] = {0: "paper", 1: "plastic"}

    def __init__(self):
        self._n = 0

    def predict(self, frame):
        self._n += 1
        if self._n <= 3:
            return [Detection(0, "paper", 0.9, (10, 10, 100, 100))]
        return []


class _SequenceInfer:
    class_names: ClassVar[dict[int, str]] = {
        0: "Organic",
        1: "Plastic bottle",
        2: "Disposable tableware",
    }

    def __init__(self):
        self._items = [
            Detection(0, "Organic", 0.92, (10, 10, 100, 100)),
            Detection(1, "Plastic bottle", 0.91, (160, 10, 260, 100)),
            Detection(2, "Disposable tableware", 0.9, (300, 10, 410, 100)),
        ]

    def predict(self, frame):
        if not self._items:
            return []
        return [self._items.pop(0)]


class _ScriptedInfer:
    class_names: ClassVar[dict[int, str]] = {
        0: "Organic",
        1: "Plastic bottle",
    }

    def __init__(self, frames):
        self._frames = list(frames)

    def predict(self, frame):
        if not self._frames:
            return []
        return list(self._frames.pop(0))


class _LowConfidencePenInfer:
    class_names: ClassVar[dict[int, str]] = {42: "Pen"}

    def predict(self, frame):
        return [Detection(42, "Pen", 0.12, (20, 20, 130, 80))]


class _SpecialistPenInfer:
    class_names: ClassVar[dict[int, str]] = {42: "Pen"}

    def predict(self, frame):
        return [
            Detection(
                42,
                "Pen",
                0.16,
                (20, 20, 130, 80),
                source=YOLO_SPECIALIST_SOURCE,
            )
        ]

    def threshold_for_detection(self, detection):
        return 0.15 if detection.source == YOLO_SPECIALIST_SOURCE else 0.4


class _NoDetectionInfer:
    class_names: ClassVar[dict[int, str]] = {}

    def predict(self, frame):
        return []


class _UnknownInfer:
    class_names: ClassVar[dict[int, str]] = {999: "Unknown object"}

    def predict(self, frame):
        return [Detection(999, "Unknown object", 0.39, (15, 12, 65, 28))]


class _OutOfTaxonomyInfer:
    class_names: ClassVar[dict[int, str]] = {123: "Mystery gadget"}

    def predict(self, frame):
        return [Detection(123, "Mystery gadget", 0.9, (20, 20, 130, 90))]


class _CardboardInfer:
    class_names: ClassVar[dict[int, str]] = {3: "Cardboard"}

    def __init__(self, xyxy: tuple[int, int, int, int]) -> None:
        self.xyxy = xyxy

    def predict(self, frame):
        return [Detection(3, "Cardboard", 0.72, self.xyxy)]


class _LowConfidenceGlassBottleInfer:
    class_names: ClassVar[dict[int, str]] = {12: "Glass bottle"}

    def predict(self, frame):
        return [Detection(12, "Glass bottle", 0.68, (5, 10, 75, 35))]


class _LowConfidencePlasticCupInfer:
    class_names: ClassVar[dict[int, str]] = {24: "Plastic cup"}

    def predict(self, frame):
        return [Detection(24, "Plastic cup", 0.12, (5, 5, 75, 35))]


class _ForkAsPenInfer:
    class_names: ClassVar[dict[int, str]] = {42: "Pen"}

    def predict(self, frame):
        return [Detection(42, "Pen", 0.68, (5, 8, 75, 36))]


class _PaperAsOrganicInfer:
    class_names: ClassVar[dict[int, str]] = {17: "Organic"}

    def predict(self, frame):
        return [Detection(17, "Organic", 0.55, (5, 5, 75, 35))]


class _OverlappingWrongPaperInfer:
    class_names: ClassVar[dict[int, str]] = {17: "Organic", 18: "Paper"}

    def predict(self, frame):
        return [
            Detection(17, "Organic", 0.55, (5, 5, 75, 35)),
            Detection(18, "Paper", 0.12, (5, 5, 75, 35)),
        ]


class _HighConfidencePenInfer:
    class_names: ClassVar[dict[int, str]] = {42: "Pen"}

    def predict(self, frame):
        return [Detection(42, "Pen", 0.95, (5, 8, 75, 36))]


class _StubUart:
    def __init__(self):
        self.sent = []
        self.silent_sent = []

    def send(self, track_id, command, conf):
        self.sent.append((track_id, command, conf))

    def send_silent(self, track_id, command, conf):
        self.silent_sent.append((track_id, command, conf))


class _WarningUart(_StubUart):
    def __init__(self):
        super().__init__()
        self.audio_tracks = []

    def send_audio_warning(self, track):
        self.audio_tracks.append(track)


class _OrderedUart(_StubUart):
    def __init__(self, events):
        super().__init__()
        self.events = events

    def send(self, track_id, command, conf):
        self.events.append(("uart", command))
        super().send(track_id, command, conf)

    def send_silent(self, track_id, command, conf):
        self.events.append(("uart_silent", command))
        super().send_silent(track_id, command, conf)


class _StubSpeaker:
    def __init__(self):
        self.spoken = []
        self.texts = []

    def speak(self, *, command, bin_index, cls_name, confidence):
        self.spoken.append((command, bin_index, cls_name, confidence))

    def speak_text(self, *, text, key, cooldown_seconds=None):
        self.texts.append((text, key, cooldown_seconds))


class _OrderedSpeaker(_StubSpeaker):
    def __init__(self, events):
        super().__init__()
        self.events = events

    def speak(self, *, command, bin_index, cls_name, confidence):
        self.events.append(("speaker", command, bin_index))
        super().speak(
            command=command,
            bin_index=bin_index,
            cls_name=cls_name,
            confidence=confidence,
        )


class _StubThreeBinClassifier:
    def __init__(self, command: str = "I", *, passed: bool = True) -> None:
        self.command = command
        self.passed = passed

    def status(self):
        return {
            "enabled": True,
            "ready": True,
            "message": "stub ready",
        }

    def classify_bgr(self, frame_bgr, xyxy):
        confidence = 0.91 if self.passed else 0.55
        return ThreeBinPrediction(
            command=self.command,
            cls_id={"O": -301, "R": -302, "I": -303}[self.command],
            cls_name=f"Kaggle 3-bin {self.command}",
            confidence=confidence,
            margin=0.3 if self.passed else 0.04,
            passed=self.passed,
            probabilities={
                "O": confidence if self.command == "O" else 0.05,
                "R": confidence if self.command == "R" else 0.04,
                "I": confidence if self.command == "I" else 0.03,
            },
            backend="stub",
        )


class _MultiClassInfer:
    class_names: ClassVar[dict[int, str]] = {42: "Pen", 37: "Textile"}

    def predict(self, frame):
        return [
            Detection(42, "Pen", 0.92, (10, 10, 100, 100)),
            Detection(37, "Textile", 0.91, (140, 10, 230, 100)),
        ]


class _SameClassPairInfer:
    class_names: ClassVar[dict[int, str]] = {42: "Pen"}

    def predict(self, frame):
        return [
            Detection(42, "Pen", 0.92, (10, 10, 100, 100)),
            Detection(42, "Pen", 0.91, (140, 10, 230, 100)),
        ]


class _OnePenInfer:
    class_names: ClassVar[dict[int, str]] = {42: "Pen"}

    def predict(self, frame):
        return [Detection(42, "Pen", 0.93, (20, 30, 120, 160))]


class _WidePenInfer:
    class_names: ClassVar[dict[int, str]] = {42: "Pen"}

    def predict(self, frame):
        return [Detection(42, "Pen", 0.93, (20, 20, 285, 205))]


class _OverlappingPaperUnknownInfer:
    class_names: ClassVar[dict[int, str]] = {18: "Paper", 999: "Unknown object"}

    def predict(self, frame):
        return [
            Detection(999, "Unknown object", 0.77, (24, 22, 338, 230)),
            Detection(18, "Paper", 0.52, (42, 45, 318, 224)),
        ]


class _TinyUnknownOnPaperInfer:
    class_names: ClassVar[dict[int, str]] = {999: "Unknown object"}

    def predict(self, frame):
        return [Detection(999, "Unknown object", 0.39, (156, 94, 186, 168))]


class _LowConfidencePaperSpoonInfer:
    class_names: ClassVar[dict[int, str]] = {18: "Paper"}

    def predict(self, frame):
        return [Detection(18, "Paper", 0.14, (8, 54, 394, 220))]


class _BlankTrayPaperInfer:
    class_names: ClassVar[dict[int, str]] = {18: "Paper"}

    def predict(self, frame):
        height, width = frame.shape[:2]
        return [Detection(18, "Paper", 0.54, (2, 2, width - 2, height - 2))]


class _BagasseAmbiguityInfer:
    class_names: ClassVar[dict[int, str]] = {17: "Organic", 19: "Paper bag"}

    def predict(self, frame):
        height, width = frame.shape[:2]
        box = (10, 10, width - 10, height - 10)
        return [
            Detection(19, "Paper bag", 0.17, box),
            Detection(17, "Organic", 0.16, box),
        ]


def _dispatch_ready_config(*, mappings=None) -> AppConfig:
    cfg = AppConfig(mappings=mappings or [])
    cfg.roi.enabled = True
    cfg.roi.x = 0
    cfg.roi.y = 0
    cfg.roi.width = 10_000
    cfg.roi.height = 10_000
    cfg.dispatch_guard.empty_rearm_seconds = 0
    cfg.dispatch_guard.empty_rearm_frames = 1
    cfg.dispatch_guard.min_sort_interval_seconds = 0
    cfg.dispatch_guard.busy_settle_seconds = 0
    cfg.dispatch_guard.min_stable_frames = 1
    return cfg


def _arm_dispatch(p: Pipeline) -> None:
    p._dispatch_guard.observe_frame(has_visible_object=False, roi_ready=True, now=time.monotonic())


def _crumpled_paper_frame() -> np.ndarray:
    frame = np.full((260, 360, 3), 228, dtype=np.uint8)
    paper = np.array(
        [
            [82, 76],
            [268, 50],
            [314, 145],
            [236, 218],
            [94, 199],
            [46, 126],
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(frame, [paper], (218, 220, 222))
    cv2.line(frame, (72, 123), (286, 87), (56, 56, 58), 18)
    cv2.line(frame, (94, 176), (250, 188), (74, 74, 76), 14)
    cv2.line(frame, (112, 88), (210, 210), (190, 190, 192), 7)
    return frame


def _metal_spoon_frame() -> np.ndarray:
    frame = np.full((260, 420, 3), 230, dtype=np.uint8)
    cv2.line(frame, (22, 174), (258, 142), (82, 82, 82), 34)
    cv2.line(frame, (22, 160), (258, 130), (168, 168, 166), 14)
    cv2.ellipse(frame, (312, 128), (74, 56), -8, 0, 360, (76, 76, 78), -1)
    cv2.ellipse(frame, (292, 122), (46, 28), -10, 0, 360, (168, 168, 166), -1)
    cv2.circle(frame, (330, 94), 12, (250, 250, 250), -1)
    cv2.circle(frame, (350, 96), 8, (245, 245, 245), -1)
    return frame


def _write_manual_reference(
    queue_dir: Path,
    *,
    cls_name: str = "Pen",
    cls_id: int = 42,
    rgb_color: tuple[int, int, int] = (220, 30, 30),
    operator_label: str = "",
    recognition_only: bool = False,
    count: int = 3,
) -> None:
    queue_dir.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        image = Image.new("RGB", (80, 40), (20, 20, 20))
        for x in range(15, 65):
            for y in range(12, 28):
                image.putpixel((x, y), rgb_color)
        img_path = queue_dir / f"manual_camera_ref_{index}.jpg"
        image.save(img_path, format="JPEG", quality=95)
        meta = {
            "source": "manual_camera_capture",
            "reviewed": True,
            "bbox_reviewed": True,
            "recognition_enabled": True,
            "recognition_only": recognition_only,
            "training_excluded": recognition_only,
            "boxes": [
                {
                    "cls_id": cls_id,
                    "cls_name": cls_name,
                    "operator_label": operator_label,
                    "conf": 1.0,
                    "xyxy": [15, 12, 65, 28],
                }
            ],
        }
        img_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")


def test_pipeline_rejects_blank_tray_paper_false_positive(tmp_path):
    cfg = _dispatch_ready_config()
    uart = _StubUart()
    p = Pipeline(cfg, _BlankTrayPaperInfer(), uart, tmp_path / "h.db")
    frame = np.full((240, 320, 3), 175, dtype=np.uint8)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert detections == []
    assert uart.sent == []
    p.close()


def test_pipeline_routes_bagasse_ambiguity_to_organic(tmp_path):
    cfg = _dispatch_ready_config()
    cfg.three_bin_classifier.enabled = True
    cfg.three_bin_classifier.mode = "unknown_only"
    cfg.three_bin_classifier.unknown_only = True
    cfg.three_bin_classifier.max_primary_confidence = 0.7
    uart = _StubUart()
    p = Pipeline(cfg, _BagasseAmbiguityInfer(), uart, tmp_path / "h.db")
    p._three_bin_classifier = _StubThreeBinClassifier("O")
    frame = np.full((240, 320, 3), 175, dtype=np.uint8)
    frame[70:180, 50:270] = (95, 145, 185)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [(item.cls_name, item.source) for item in detections] == [("Organic", THREE_BIN_SOURCE)]
    assert uart.sent == [(1, "O", detections[0].conf)]
    p.close()


def test_pipeline_labels_unknown_with_reviewed_manual_reference(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("TRASH_SORTER_REFERENCE_EMBEDDER", "legacy")
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Pen", command="R", bin_index=2)]
    )
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.model.conf_threshold = 0.3
    cfg.manual_reference_recognition.allow_unknown_matches = True
    cfg.manual_reference_recognition.min_similarity = 0.9
    cfg.manual_reference_recognition.top_k = 3
    cfg.manual_reference_recognition.min_votes = 3
    _write_manual_reference(Path(cfg.capture.output_dir) / "low_conf_queue")
    uart = _StubUart()
    p = Pipeline(cfg, _UnknownInfer(), uart, tmp_path / "h.db")
    p.set_hardware_dispatch_enabled(False)
    frame = np.zeros((40, 80, 3), dtype=np.uint8)
    frame[:, :] = (20, 20, 20)
    frame[12:28, 15:65] = (30, 30, 220)

    detections = p.process_frame(frame, datetime.now(UTC))

    assert [d.cls_name for d in detections] == ["Pen"]
    assert detections[0].source == "manual_reference"
    assert detections[0].conf >= 0.9
    assert uart.sent == []


def test_pipeline_labels_unknown_with_one_fresh_reviewed_reference(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("TRASH_SORTER_REFERENCE_EMBEDDER", "legacy")
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Pen", command="R", bin_index=2)]
    )
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.model.conf_threshold = 0.3
    cfg.manual_reference_recognition.allow_unknown_matches = True
    cfg.manual_reference_recognition.unknown_min_similarity = 0.92
    cfg.manual_reference_recognition.unknown_min_votes = 1
    _write_manual_reference(Path(cfg.capture.output_dir) / "low_conf_queue", count=1)
    uart = _StubUart()
    p = Pipeline(cfg, _UnknownInfer(), uart, tmp_path / "h.db")
    p.set_hardware_dispatch_enabled(False)
    frame = np.zeros((40, 80, 3), dtype=np.uint8)
    frame[:, :] = (20, 20, 20)
    frame[12:28, 15:65] = (30, 30, 220)

    detections = p.process_frame(frame, datetime.now(UTC))

    assert [(d.cls_name, d.source) for d in detections] == [("Pen", "manual_reference")]
    assert detections[0].conf >= 0.92
    assert uart.sent == []
    p.close()


def test_pipeline_routes_unknown_with_legacy_common_reference_alias(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("TRASH_SORTER_REFERENCE_EMBEDDER", "legacy")
    cfg = _dispatch_ready_config()
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.model.conf_threshold = 0.3
    cfg.manual_reference_recognition.allow_unknown_matches = True
    cfg.manual_reference_recognition.min_similarity = 0.9
    cfg.manual_reference_recognition.top_k = 3
    cfg.manual_reference_recognition.min_votes = 3
    _write_manual_reference(
        Path(cfg.capture.output_dir) / "low_conf_queue",
        cls_name="lon nuoc",
        cls_id=0,
        rgb_color=(30, 90, 230),
    )
    uart = _StubUart()
    p = Pipeline(cfg, _UnknownInfer(), uart, tmp_path / "h.db")
    frame = np.zeros((40, 80, 3), dtype=np.uint8)
    frame[:, :] = (20, 20, 20)
    frame[12:28, 15:65] = (230, 90, 30)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [d.cls_name for d in detections] == ["Aluminum can"]
    assert uart.sent == [(1, "I", detections[0].conf)]


def test_pipeline_dispatches_object_already_on_tray_when_auto_sort_is_enabled(tmp_path):
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Pen", command="R", bin_index=2)]
    )
    uart = _StubUart()
    p = Pipeline(cfg, _OnePenInfer(), uart, tmp_path / "h.db")
    p.reset_dispatch_state(arm_immediately=True)
    frame = np.zeros((220, 320, 3), dtype=np.uint8)

    detections = p.process_frame(frame, datetime.now(UTC))

    assert [d.cls_name for d in detections] == ["Pen"]
    assert uart.sent == [(1, "R", detections[0].conf)]


def test_pipeline_dispatches_next_new_object_after_ack_and_empty_tray(tmp_path):
    cfg = _dispatch_ready_config()
    uart = _StubUart()
    p = Pipeline(cfg, _SequenceInfer(), uart, tmp_path / "h.db")
    p.reset_dispatch_state(arm_immediately=True)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    p.process_frame(frame, datetime.now(UTC))
    first_track, first_command, _ = uart.sent[0]
    p.on_ack(first_track, first_command, "ok", 3200)
    p._dispatch_guard.observe_frame(
        has_visible_object=False,
        roi_ready=True,
        now=time.monotonic(),
    )
    p.process_frame(frame, datetime.now(UTC))

    assert [item[1] for item in uart.sent] == ["O", "I"]


def test_pipeline_clears_emitted_track_after_empty_rearm_for_next_object(tmp_path):
    cfg = _dispatch_ready_config()
    uart = _StubUart()
    same_box = (10, 10, 100, 100)
    p = Pipeline(
        cfg,
        _ScriptedInfer(
            [
                [Detection(0, "Organic", 0.92, same_box)],
                [],
                [Detection(1, "Plastic bottle", 0.91, same_box)],
            ]
        ),
        uart,
        tmp_path / "h.db",
    )
    p.reset_dispatch_state(arm_immediately=True)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    p.process_frame(frame, datetime.now(UTC))
    first_track, first_command, _ = uart.sent[0]
    p.on_ack(first_track, first_command, "ok", 3200)
    p.process_frame(frame, datetime.now(UTC))
    p.process_frame(frame, datetime.now(UTC))

    assert [item[1] for item in uart.sent] == ["O", "I"]
    p.close()


def test_pipeline_corrects_large_cardboard_cloth_to_textile_reference(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("TRASH_SORTER_REFERENCE_EMBEDDER", "legacy")
    cfg = _dispatch_ready_config(
        mappings=[
            ClassMapping(class_name="Cardboard", command="I", bin_index=3),
            ClassMapping(class_name="Textile", command="R", bin_index=2),
        ]
    )
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.model.conf_threshold = 0.3
    cfg.manual_reference_recognition.min_similarity = 0.9
    cfg.manual_reference_recognition.top_k = 3
    cfg.manual_reference_recognition.min_votes = 3
    _write_manual_reference(
        Path(cfg.capture.output_dir) / "low_conf_queue",
        cls_name="Textile",
        cls_id=37,
        rgb_color=(180, 180, 180),
    )
    uart = _StubUart()
    p = Pipeline(cfg, _CardboardInfer((10, 10, 90, 90)), uart, tmp_path / "h.db")
    p.set_hardware_dispatch_enabled(False)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[:, :] = (20, 20, 20)
    frame[10:90, 10:90] = (180, 180, 180)

    detections = p.process_frame(frame, datetime.now(UTC))

    assert [d.cls_name for d in detections] == ["Textile"]
    assert detections[0].source == "manual_reference"
    mapping = p._mapping_for_detection(detections[0])
    assert (mapping.command, mapping.bin_index) == ("R", 2)
    assert uart.sent == []


def test_pipeline_keeps_small_cardboard_detection_without_reference_correction(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("TRASH_SORTER_REFERENCE_EMBEDDER", "legacy")
    cfg = _dispatch_ready_config(
        mappings=[
            ClassMapping(class_name="Cardboard", command="I", bin_index=3),
            ClassMapping(class_name="Textile", command="R", bin_index=2),
        ]
    )
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.model.conf_threshold = 0.3
    cfg.manual_reference_recognition.min_similarity = 0.9
    cfg.manual_reference_recognition.top_k = 3
    cfg.manual_reference_recognition.min_votes = 3
    _write_manual_reference(
        Path(cfg.capture.output_dir) / "low_conf_queue",
        cls_name="Textile",
        cls_id=37,
        rgb_color=(180, 180, 180),
    )
    uart = _StubUart()
    p = Pipeline(cfg, _CardboardInfer((20, 20, 40, 40)), uart, tmp_path / "h.db")
    p.set_hardware_dispatch_enabled(False)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[:, :] = (20, 20, 20)
    frame[10:90, 10:90] = (180, 180, 180)

    detections = p.process_frame(frame, datetime.now(UTC))

    assert [d.cls_name for d in detections] == ["Cardboard"]
    assert detections[0].source == "YOLO"
    mapping = p._mapping_for_detection(detections[0])
    assert (mapping.command, mapping.bin_index) == ("I", 3)
    assert uart.sent == []


def test_pipeline_rejects_non_textile_reference_for_cardboard_correction(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("TRASH_SORTER_REFERENCE_EMBEDDER", "legacy")
    cfg = _dispatch_ready_config(
        mappings=[
            ClassMapping(class_name="Cardboard", command="I", bin_index=3),
            ClassMapping(class_name="Pen", command="R", bin_index=2),
        ]
    )
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.model.conf_threshold = 0.3
    cfg.manual_reference_recognition.min_similarity = 0.9
    cfg.manual_reference_recognition.top_k = 3
    cfg.manual_reference_recognition.min_votes = 3
    _write_manual_reference(
        Path(cfg.capture.output_dir) / "low_conf_queue",
        cls_name="Pen",
        cls_id=42,
        rgb_color=(180, 180, 180),
    )
    uart = _StubUart()
    p = Pipeline(cfg, _CardboardInfer((10, 10, 90, 90)), uart, tmp_path / "h.db")
    p.set_hardware_dispatch_enabled(False)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[:, :] = (20, 20, 20)
    frame[10:90, 10:90] = (180, 180, 180)

    detections = p.process_frame(frame, datetime.now(UTC))

    assert [d.cls_name for d in detections] == ["Cardboard"]
    assert detections[0].source == "YOLO"
    assert uart.sent == []


def test_pipeline_corrects_glass_bottle_to_wooden_spoon(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("TRASH_SORTER_REFERENCE_EMBEDDER", "legacy")
    cfg = _dispatch_ready_config()
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.model.conf_threshold = 0.05
    cfg.manual_reference_recognition.min_similarity = 0.9
    cfg.manual_reference_recognition.top_k = 3
    cfg.manual_reference_recognition.min_votes = 3
    cfg.manual_reference_recognition.min_correction_area_ratio = 0.2
    _write_manual_reference(
        Path(cfg.capture.output_dir) / "low_conf_queue",
        cls_name="Wood",
        cls_id=40,
        rgb_color=(180, 140, 80),
        operator_label="Thìa gỗ",
        recognition_only=True,
    )
    uart = _StubUart()
    p = Pipeline(cfg, _LowConfidenceGlassBottleInfer(), uart, tmp_path / "h.db")
    frame = np.zeros((40, 80, 3), dtype=np.uint8)
    frame[:, :] = (20, 20, 20)
    frame[10:35, 5:75] = (80, 140, 180)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [(d.cls_name, d.operator_label) for d in detections] == [("Wood", "Thìa gỗ")]
    assert uart.sent == [(1, "R", detections[0].conf)]


def test_pipeline_corrects_pen_to_disposable_fork(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("TRASH_SORTER_REFERENCE_EMBEDDER", "legacy")
    cfg = _dispatch_ready_config()
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.model.conf_threshold = 0.05
    cfg.manual_reference_recognition.min_similarity = 0.9
    cfg.manual_reference_recognition.top_k = 3
    cfg.manual_reference_recognition.min_votes = 3
    cfg.manual_reference_recognition.min_correction_area_ratio = 0.2
    _write_manual_reference(
        Path(cfg.capture.output_dir) / "low_conf_queue",
        cls_name="Disposable tableware",
        cls_id=8,
        rgb_color=(60, 60, 60),
        operator_label="Nĩa nhựa dùng một lần",
        recognition_only=True,
    )
    uart = _StubUart()
    p = Pipeline(cfg, _ForkAsPenInfer(), uart, tmp_path / "h.db")
    frame = np.full((40, 80, 3), 220, dtype=np.uint8)
    frame[8:36, 5:75] = (60, 60, 60)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [(d.cls_name, d.operator_label) for d in detections] == [
        ("Disposable tableware", "Nĩa nhựa dùng một lần")
    ]
    assert uart.sent == [(1, "R", detections[0].conf)]
    rows = p.history.query(limit=1)
    meta = json.loads(Path(rows[0].meta_path).read_text(encoding="utf-8"))
    assert meta["display_name"] == "Nĩa nhựa dùng một lần"
    assert meta["review_required"] is False
    p.close()


def test_pipeline_rescues_low_conf_plastic_cup_as_metal_utensil(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("TRASH_SORTER_REFERENCE_EMBEDDER", "legacy")
    cfg = _dispatch_ready_config()
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.model.conf_threshold = 0.4
    cfg.manual_reference_recognition.min_similarity = 0.9
    cfg.manual_reference_recognition.top_k = 3
    cfg.manual_reference_recognition.min_votes = 3
    cfg.manual_reference_recognition.min_correction_area_ratio = 0.2
    _write_manual_reference(
        Path(cfg.capture.output_dir) / "low_conf_queue",
        cls_name="Iron utensils",
        cls_id=13,
        rgb_color=(70, 70, 70),
        operator_label="Nia kim loai",
        recognition_only=True,
    )
    uart = _StubUart()
    p = Pipeline(cfg, _LowConfidencePlasticCupInfer(), uart, tmp_path / "h.db")
    frame = np.full((40, 80, 3), 220, dtype=np.uint8)
    frame[5:35, 5:75] = (70, 70, 70)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [(d.cls_name, d.operator_label, d.source) for d in detections] == [
        ("Iron utensils", "Nia kim loai", "manual_reference")
    ]
    assert uart.sent == [(1, "R", detections[0].conf)]
    p.close()


def test_pipeline_general_reference_correction_rescues_wrong_yolo_class(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("TRASH_SORTER_REFERENCE_EMBEDDER", "legacy")
    cfg = _dispatch_ready_config(
        mappings=[
            ClassMapping(class_name="Organic", command="O", bin_index=1),
            ClassMapping(class_name="Paper", command="I", bin_index=3),
        ]
    )
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.model.conf_threshold = 0.3
    cfg.manual_reference_recognition.min_similarity = 0.9
    cfg.manual_reference_recognition.top_k = 3
    cfg.manual_reference_recognition.min_votes = 3
    cfg.manual_reference_recognition.min_correction_area_ratio = 0.2
    _write_manual_reference(
        Path(cfg.capture.output_dir) / "low_conf_queue",
        cls_name="Paper",
        cls_id=18,
        rgb_color=(210, 210, 210),
        recognition_only=True,
    )
    uart = _StubUart()
    p = Pipeline(cfg, _PaperAsOrganicInfer(), uart, tmp_path / "h.db")
    frame = np.full((40, 80, 3), 20, dtype=np.uint8)
    frame[5:35, 5:75] = (210, 210, 210)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [(d.cls_name, d.source) for d in detections] == [("Paper", "manual_reference")]
    assert uart.sent == [(1, "I", detections[0].conf)]
    p.close()


def test_pipeline_manual_reference_rescues_overlapping_low_conf_raw_candidate(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("TRASH_SORTER_REFERENCE_EMBEDDER", "legacy")
    cfg = _dispatch_ready_config(
        mappings=[
            ClassMapping(class_name="Organic", command="O", bin_index=1),
            ClassMapping(class_name="Paper", command="I", bin_index=3),
        ]
    )
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.model.conf_threshold = 0.3
    cfg.manual_reference_recognition.min_similarity = 0.9
    cfg.manual_reference_recognition.top_k = 3
    cfg.manual_reference_recognition.min_votes = 3
    cfg.manual_reference_recognition.min_correction_area_ratio = 0.2
    _write_manual_reference(
        Path(cfg.capture.output_dir) / "low_conf_queue",
        cls_name="Paper",
        cls_id=18,
        rgb_color=(210, 210, 210),
        recognition_only=True,
    )
    uart = _StubUart()
    p = Pipeline(cfg, _OverlappingWrongPaperInfer(), uart, tmp_path / "h.db")
    frame = np.full((40, 80, 3), 20, dtype=np.uint8)
    frame[5:35, 5:75] = (210, 210, 210)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [(d.cls_name, d.source) for d in detections] == [("Paper", "manual_reference")]
    assert uart.sent == [(1, "I", detections[0].conf)]
    p.close()


def test_pipeline_keeps_high_confidence_pen_despite_fork_reference(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("TRASH_SORTER_REFERENCE_EMBEDDER", "legacy")
    cfg = _dispatch_ready_config()
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.model.conf_threshold = 0.05
    _write_manual_reference(
        Path(cfg.capture.output_dir) / "low_conf_queue",
        cls_name="Disposable tableware",
        cls_id=8,
        rgb_color=(60, 60, 60),
        operator_label="Nĩa nhựa dùng một lần",
        recognition_only=True,
    )
    uart = _StubUart()
    p = Pipeline(cfg, _HighConfidencePenInfer(), uart, tmp_path / "h.db")
    frame = np.full((40, 80, 3), 220, dtype=np.uint8)
    frame[8:36, 5:75] = (60, 60, 60)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [(d.cls_name, d.operator_label) for d in detections] == [("Pen", "")]
    assert uart.sent == [(1, "R", 0.95)]
    p.close()


def test_pipeline_routes_unknown_with_kaggle_three_bin_classifier(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.model.conf_threshold = 0.3
    cfg.three_bin_classifier.enabled = True
    cfg.three_bin_classifier.unknown_only = True
    uart = _StubUart()
    p = Pipeline(cfg, _UnknownInfer(), uart, tmp_path / "h.db")
    p._three_bin_classifier = _StubThreeBinClassifier()
    frame = np.zeros((40, 80, 3), dtype=np.uint8)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [d.cls_name for d in detections] == ["Kaggle 3-bin I"]
    assert detections[0].source == THREE_BIN_SOURCE
    assert uart.sent == [(1, "I", detections[0].conf)]
    rows = p.history.query(limit=1)
    assert len(rows) == 1
    assert rows[0].cls_name == "Kaggle 3-bin I"
    meta = json.loads(Path(rows[0].meta_path).read_text(encoding="utf-8"))
    assert meta["display_name"] == "Nhóm Tái chế (chưa xác định vật cụ thể)"
    assert meta["review_required"] is True
    assert meta["training_excluded"] is True
    p.close()


def test_pipeline_corrects_crumpled_paper_before_three_bin_inorganic_fallback(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Paper", command="I", bin_index=3)]
    )
    cfg.model.conf_threshold = 0.3
    cfg.three_bin_classifier.enabled = True
    cfg.three_bin_classifier.unknown_only = True
    infer = _ScriptedInfer([[Detection(999, "Unknown object", 0.77, (42, 45, 318, 224))]])
    uart = _StubUart()
    p = Pipeline(cfg, infer, uart, tmp_path / "h.db")
    p._three_bin_classifier = _StubThreeBinClassifier("R")
    frame = _crumpled_paper_frame()

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [(item.cls_name, item.source) for item in detections] == [
        ("Paper", "visual_correction:crumpled_paper")
    ]
    assert uart.sent == [(1, "I", detections[0].conf)]
    p.close()


def test_pipeline_keeps_generic_three_bin_organic_non_specific(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.model.conf_threshold = 0.3
    cfg.three_bin_classifier.enabled = True
    cfg.three_bin_classifier.unknown_only = True
    uart = _StubUart()
    p = Pipeline(cfg, _UnknownInfer(), uart, tmp_path / "h.db")
    p._three_bin_classifier = _StubThreeBinClassifier("O")
    frame = np.zeros((40, 80, 3), dtype=np.uint8)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [(item.cls_id, item.cls_name) for item in detections] == [(-301, "Kaggle 3-bin O")]
    assert uart.sent == [(1, "O", detections[0].conf)]
    rows = p.history.query(limit=1)
    assert len(rows) == 1
    assert rows[0].cls_name == "Kaggle 3-bin O"
    p.close()


def test_three_bin_display_name_does_not_claim_an_exact_class():
    assert three_bin_display_name("Kaggle 3-bin O") == "Nhóm Hữu cơ (chưa xác định vật cụ thể)"
    assert three_bin_display_name("Kaggle 3-bin I") == "Nhóm Tái chế (chưa xác định vật cụ thể)"
    assert three_bin_display_name("Plastic bottle") == "Plastic bottle"


def test_three_bin_does_not_override_a_known_primary_route(tmp_path, monkeypatch):
    class _LowConfidenceOrganicInfer:
        class_names: ClassVar[dict[int, str]] = {0: "Organic"}

        def predict(self, _frame):
            return [Detection(0, "Organic", 0.4, (10, 10, 100, 100))]

    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.model.conf_threshold = 0.3
    cfg.three_bin_classifier.enabled = True
    cfg.three_bin_classifier.unknown_only = True
    cfg.three_bin_classifier.max_primary_confidence = 0.45
    uart = _StubUart()
    p = Pipeline(cfg, _LowConfidenceOrganicInfer(), uart, tmp_path / "h.db")
    p._three_bin_classifier = _StubThreeBinClassifier("I")
    frame = np.zeros((120, 120, 3), dtype=np.uint8)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [d.cls_name for d in detections] == ["Organic"]
    assert uart.sent == [(1, "O", detections[0].conf)]


def test_pipeline_uses_lower_threshold_for_plastic_bottle(tmp_path, monkeypatch):
    class _LowConfidenceBottleInfer:
        class_names: ClassVar[dict[int, str]] = {0: "Organic", 1: "Plastic bottle"}

        def predict(self, _frame):
            return [
                Detection(0, "Organic", 0.22, (10, 10, 100, 100)),
                Detection(1, "Plastic bottle", 0.31, (10, 10, 100, 100)),
            ]

    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.model.conf_threshold = 0.39
    uart = _StubUart()
    p = Pipeline(cfg, _LowConfidenceBottleInfer(), uart, tmp_path / "h.db")
    frame = np.zeros((120, 120, 3), dtype=np.uint8)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [d.cls_name for d in detections] == ["Plastic bottle"]
    assert uart.sent == [(1, "I", detections[0].conf)]


def test_pipeline_route_consensus_allows_matching_secondary_route(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)]
    )
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.three_bin_classifier.enabled = True
    cfg.three_bin_classifier.mode = "route_consensus"
    cfg.three_bin_classifier.unknown_only = False
    uart = _StubUart()
    p = Pipeline(cfg, _StubInfer(), uart, tmp_path / "h.db")
    p._three_bin_classifier = _StubThreeBinClassifier("I")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    for _ in range(3):
        p.process_frame(frame, datetime.now(UTC))

    assert uart.sent == [(1, "I", 0.9)]
    p.close()


def test_pipeline_route_consensus_blocks_disagreement_and_saves_review(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)]
    )
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.three_bin_classifier.enabled = True
    cfg.three_bin_classifier.mode = "route_consensus"
    cfg.three_bin_classifier.unknown_only = False
    uart = _StubUart()
    p = Pipeline(cfg, _StubInfer(), uart, tmp_path / "h.db")
    p._three_bin_classifier = _StubThreeBinClassifier("R")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert detections[0].route_consensus == "blocked"
    assert detections[0].secondary_route == "R"
    assert p.dispatch_status == "route disagreement I->R"
    assert uart.sent == []
    queue = Path(cfg.capture.output_dir) / "low_conf_queue"
    reviews = list(queue.glob("route_consensus_*.json"))
    assert len(reviews) == 1
    review = json.loads(reviews[0].read_text(encoding="utf-8"))
    assert review["training_exclusion_reason"] == "route_consensus_blocked"
    assert review["route_consensus"]["primary_route"] == "I"
    assert review["route_consensus"]["secondary_route"] == "R"
    p.close()


def test_pipeline_emits_one_command_per_object(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)]
    )
    speaker = _StubSpeaker()
    p = Pipeline(
        cfg=cfg,
        engine=_StubInfer(),
        uart=_StubUart(),
        history_db=tmp_path / "h.db",
        speaker=speaker,
    )
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    _arm_dispatch(p)
    for _ in range(3):
        p.process_frame(frame, ts=datetime.now(UTC))
    assert len(p.uart.sent) == 1
    assert p.uart.sent[0][1] == "I"
    assert speaker.spoken == []
    p.on_ack(p.uart.sent[0][0], p.uart.sent[0][1], "ok", 12)
    assert speaker.spoken == []
    row = p.history.query(limit=1)[0]
    assert row.uart_command == "I"
    assert row.bin_index == 3
    p.close()


def test_pipeline_speaks_on_uart_send_when_computer_speaker_selected(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)]
    )
    cfg.speaker.output_mode = "computer_speaker"
    cfg.speaker.enabled = True
    speaker = _StubSpeaker()
    p = Pipeline(
        cfg=cfg,
        engine=_StubInfer(),
        uart=_StubUart(),
        history_db=tmp_path / "h.db",
        speaker=speaker,
    )
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    _arm_dispatch(p)
    for _ in range(3):
        p.process_frame(frame, ts=datetime.now(UTC))
    assert p.uart.sent == []
    assert len(p.uart.silent_sent) == 1
    assert speaker.spoken == [("I", 3, "paper", 0.9)]
    p.on_ack(p.uart.silent_sent[0][0], p.uart.silent_sent[0][1], "ok", 12)
    assert speaker.spoken == [("I", 3, "paper", 0.9)]
    row = p.history.query(limit=1)[0]
    assert row.uart_command == "I"
    assert row.bin_index == 3
    p.close()


def test_pipeline_computer_speaker_fires_immediately_before_uart_send(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)]
    )
    cfg.speaker.output_mode = "computer_speaker"
    cfg.speaker.enabled = True
    events = []
    uart = _OrderedUart(events)
    speaker = _OrderedSpeaker(events)
    p = Pipeline(
        cfg=cfg,
        engine=_StubInfer(),
        uart=uart,
        history_db=tmp_path / "h.db",
        speaker=speaker,
    )
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    for _ in range(3):
        p.process_frame(frame, ts=datetime.now(UTC))

    assert events == [("speaker", "I", 3), ("uart_silent", "I")]
    assert speaker.spoken == [("I", 3, "paper", 0.9)]
    assert uart.sent == []
    assert uart.silent_sent == [(1, "I", 0.9)]
    p.close()


def test_pipeline_routes_three_representative_classes_to_three_bins(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[
            ClassMapping(class_name="Organic", command="O", bin_index=1),
            ClassMapping(class_name="Plastic bottle", command="R", bin_index=2),
            ClassMapping(class_name="Disposable tableware", command="R", bin_index=2),
        ]
    )
    cfg.speaker.output_mode = "computer_speaker"
    cfg.speaker.enabled = True
    uart = _StubUart()
    speaker = _StubSpeaker()
    p = Pipeline(
        cfg=cfg,
        engine=_SequenceInfer(),
        uart=uart,
        history_db=tmp_path / "h.db",
        speaker=speaker,
    )
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    for index in range(3):
        _arm_dispatch(p)
        p.process_frame(frame, ts=datetime(2026, 6, 2, 8, index, tzinfo=UTC))
        assert (
            speaker.spoken[index]
            == [
                ("O", 1, "Organic", 0.92),
                ("I", 3, "Plastic bottle", 0.91),
                ("R", 2, "Disposable tableware", 0.9),
            ][index]
        )
        track_id, command, _conf = uart.silent_sent[-1]
        p.on_ack(track_id, command, "ok", 15)

    assert uart.sent == []
    assert [item[1] for item in uart.silent_sent] == ["O", "I", "R"]
    rows = list(reversed(p.history.query(limit=10)))
    expected_route_names = [
        category_for_command(command).name
        for command in ("O", "I", "R")
        if category_for_command(command) is not None
    ]
    assert [(row.cls_name, row.route_label, row.bin_index, row.uart_command) for row in rows] == [
        ("Organic", expected_route_names[0], 1, "O"),
        ("Plastic bottle", expected_route_names[1], 3, "I"),
        ("Disposable tableware", expected_route_names[2], 2, "R"),
    ]
    assert [row.ack_status for row in rows] == ["ok", "ok", "ok"]
    assert [(item[0], item[1], item[2]) for item in speaker.spoken] == [
        ("O", 1, "Organic"),
        ("I", 3, "Plastic bottle"),
        ("R", 2, "Disposable tableware"),
    ]
    rows_after_ack = list(reversed(p.history.query(limit=10)))
    assert [row.ack_status for row in rows_after_ack] == ["ok", "ok", "ok"]
    assert [row.rtt_ms for row in rows_after_ack] == [15, 15, 15]
    p.close()


def test_pipeline_blocks_dispatch_and_warns_for_multiple_classes_in_roi(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.dispatch_guard.multi_class_warning_cooldown_seconds = 5.0
    uart = _WarningUart()
    speaker = _StubSpeaker()
    p = Pipeline(cfg, _MultiClassInfer(), uart, tmp_path / "h.db", speaker=speaker)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))
    p.process_frame(frame, ts=datetime.now(UTC))

    assert {item.cls_name for item in detections} == {"Pen", "Textile"}
    assert p.dispatch_status == "multiple waste types"
    assert uart.sent == []
    assert uart.audio_tracks == [8]
    assert p.history.query(limit=10) == []
    assert speaker.spoken == []
    assert speaker.texts == []
    p.close()


def test_pipeline_warns_for_multiple_classes_when_hardware_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.dispatch_guard.multi_class_warning_cooldown_seconds = 5.0
    uart = _WarningUart()
    speaker = _StubSpeaker()
    p = Pipeline(cfg, _MultiClassInfer(), uart, tmp_path / "h.db", speaker=speaker)
    p.set_hardware_dispatch_enabled(False)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert {item.cls_name for item in detections} == {"Pen", "Textile"}
    assert p.dispatch_status == "multiple waste types"
    assert uart.sent == []
    assert uart.audio_tracks == []
    assert p.history.query(limit=10) == []
    assert speaker.spoken == []
    assert speaker.texts == []
    p.close()


def test_pipeline_warns_on_computer_speaker_when_selected(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.speaker.output_mode = "computer_speaker"
    cfg.speaker.enabled = True
    cfg.dispatch_guard.multi_class_warning_cooldown_seconds = 5.0
    uart = _WarningUart()
    speaker = _StubSpeaker()
    p = Pipeline(cfg, _MultiClassInfer(), uart, tmp_path / "h.db", speaker=speaker)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert {item.cls_name for item in detections} == {"Pen", "Textile"}
    assert p.dispatch_status == "multiple waste types"
    assert uart.sent == []
    assert uart.audio_tracks == []
    assert p.history.query(limit=10) == []
    assert speaker.spoken == []
    assert speaker.texts == [
        (MULTI_CLASS_WARNING_TEXT, "multi_class_dispatch_blocked", 5.0),
    ]
    p.close()


def test_pipeline_suppresses_detection_and_warning_while_sort_is_busy(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.speaker.output_mode = "computer_speaker"
    cfg.speaker.enabled = True
    uart = _StubUart()
    speaker = _StubSpeaker()
    p = Pipeline(cfg, _StubInfer(), uart, tmp_path / "h.db", speaker=speaker)
    p.reset_dispatch_state(arm_immediately=True)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    first = p.process_frame(frame, ts=datetime.now(UTC))
    p.engine = _MultiClassInfer()
    during_sort = p.process_frame(frame, ts=datetime.now(UTC))

    assert [item.cls_name for item in first] == ["paper"]
    assert during_sort == []
    assert speaker.spoken == [("I", 3, "paper", 0.9)]
    assert speaker.texts == []
    assert len(uart.silent_sent) == 1
    p.close()


def test_pipeline_blocks_two_objects_of_same_class_in_roi(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Pen", command="R", bin_index=2)]
    )
    uart = _StubUart()
    speaker = _StubSpeaker()
    p = Pipeline(cfg, _SameClassPairInfer(), uart, tmp_path / "h.db", speaker=speaker)
    p.set_hardware_dispatch_enabled(False)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert [item.cls_name for item in detections] == ["Pen", "Pen"]
    assert p.dispatch_status == "multiple waste types"
    assert uart.sent == []
    assert p.history.query(limit=10) == []
    assert speaker.texts == []
    p.close()


def test_pipeline_blocks_two_foreground_objects_when_yolo_sees_one(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Pen", command="R", bin_index=2)]
    )
    uart = _StubUart()
    speaker = _StubSpeaker()
    p = Pipeline(cfg, _OnePenInfer(), uart, tmp_path / "h.db", speaker=speaker)
    p.set_hardware_dispatch_enabled(False)
    frame = np.full((240, 320, 3), 245, dtype=np.uint8)
    frame[24:164, 24:92] = (35, 35, 35)
    frame[56:200, 160:280] = (210, 85, 35)

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert [item.cls_name for item in detections] == ["Pen"]
    assert p.dispatch_status == "multiple waste types (2 visible objects)"
    assert uart.sent == []
    assert p.history.query(limit=10) == []
    assert speaker.texts == []
    p.close()


def test_pipeline_allows_split_foreground_inside_one_yolo_object(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Pen", command="R", bin_index=2)]
    )
    p = Pipeline(cfg, _WidePenInfer(), _StubUart(), tmp_path / "h.db", speaker=_StubSpeaker())
    p.set_hardware_dispatch_enabled(False)
    frame = np.full((240, 320, 3), 245, dtype=np.uint8)
    frame[24:164, 24:92] = (35, 35, 35)
    frame[56:200, 160:280] = (210, 85, 35)

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert [item.cls_name for item in detections] == ["Pen"]
    assert p.dispatch_status == "TEST OFF"
    assert p.uart.sent == []
    p.close()


def test_pipeline_collapses_overlapping_labels_for_one_paper_object(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Paper", command="I", bin_index=3)]
    )
    cfg.model.conf_threshold = 0.3
    uart = _StubUart()
    speaker = _StubSpeaker()
    p = Pipeline(cfg, _OverlappingPaperUnknownInfer(), uart, tmp_path / "h.db", speaker=speaker)
    p.set_hardware_dispatch_enabled(False)
    frame = _crumpled_paper_frame()

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert [item.cls_name for item in detections] == ["Paper"]
    assert p.dispatch_status == "TEST OFF"
    assert uart.sent == []
    assert speaker.texts == []
    p.close()


def test_pipeline_expands_tiny_unknown_fold_and_allows_one_crumpled_paper(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Paper", command="I", bin_index=3)]
    )
    cfg.model.conf_threshold = 0.3
    uart = _StubUart()
    speaker = _StubSpeaker()
    p = Pipeline(cfg, _TinyUnknownOnPaperInfer(), uart, tmp_path / "h.db", speaker=speaker)
    p.set_hardware_dispatch_enabled(False)
    frame = _crumpled_paper_frame()

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert [(item.cls_name, item.source) for item in detections] == [
        ("Paper", "visual_correction:crumpled_paper")
    ]
    assert p.dispatch_status == "TEST OFF"
    assert uart.sent == []
    assert speaker.texts == []
    p.close()


def test_pipeline_routes_low_conf_paper_like_spoon_as_inorganic_utensil(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.model.conf_threshold = 0.4
    cfg.unknown_fallback.stable_frames = 1
    uart = _StubUart()
    speaker = _StubSpeaker()
    p = Pipeline(cfg, _LowConfidencePaperSpoonInfer(), uart, tmp_path / "h.db", speaker=speaker)
    p.set_hardware_dispatch_enabled(False)

    _arm_dispatch(p)
    detections = p.process_frame(_metal_spoon_frame(), ts=datetime.now(UTC))

    assert [(item.cls_name, item.source, item.operator_label) for item in detections] == [
        ("Iron utensils", "visual_correction:metal_utensil", "Muong kim loai")
    ]
    assert p._mapping_for_detection(detections[0]).command == "R"
    assert p.dispatch_status == "TEST OFF"
    assert uart.sent == []
    assert speaker.texts == []
    p.close()


def test_pipeline_blocks_low_conf_visual_metal_utensil_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.model.conf_threshold = 0.4
    cfg.unknown_fallback.stable_frames = 1
    uart = _StubUart()
    p = Pipeline(cfg, _LowConfidencePaperSpoonInfer(), uart, tmp_path / "h.db")

    _arm_dispatch(p)
    detections = p.process_frame(_metal_spoon_frame(), ts=datetime.now(UTC))

    assert [(item.cls_name, item.source) for item in detections] == [
        ("Iron utensils", "visual_correction:metal_utensil")
    ]
    assert p.dispatch_status == "low confidence review required"
    assert uart.sent == []
    assert p.history.query(limit=10) == []
    p.close()


def test_pipeline_blocks_full_frame_multi_object_when_roi_misses_one(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Pen", command="R", bin_index=2)]
    )
    cfg.roi.x = 0
    cfg.roi.y = 0
    cfg.roi.width = 120
    cfg.roi.height = 120
    uart = _StubUart()
    speaker = _StubSpeaker()
    p = Pipeline(cfg, _OnePenInfer(), uart, tmp_path / "h.db", speaker=speaker)
    p.set_hardware_dispatch_enabled(False)
    frame = np.full((240, 320, 3), 245, dtype=np.uint8)
    frame[24:164, 24:92] = (35, 35, 35)
    frame[56:200, 160:280] = (210, 85, 35)

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert [item.cls_name for item in detections] == ["Pen"]
    assert p.dispatch_status == "multiple waste types (2 visible objects)"
    assert uart.sent == []
    assert p.history.query(limit=10) == []
    p.close()


def test_pipeline_routes_unmapped_known_class(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    p = Pipeline(cfg, _StubInfer(), _StubUart(), tmp_path / "h.db")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    _arm_dispatch(p)
    p.process_frame(frame, ts=datetime.now(UTC))
    assert p.uart.sent == [(1, "I", 0.9)]
    row = p.history.query(limit=1)[0]
    assert row.cls_name == "paper"
    assert row.uart_command == "I"
    assert row.bin_index == 3
    p.close()


def test_pipeline_renders_but_does_not_dispatch_when_hardware_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    uart = _StubUart()
    p = Pipeline(cfg, _StubInfer(), uart, tmp_path / "h.db")
    p.set_hardware_dispatch_enabled(False)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert len(detections) == 1
    assert uart.sent == []
    assert p.history.query(limit=10) == []
    p.close()


def test_pipeline_roi_disabled_renders_but_blocks_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = AppConfig(mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)])
    uart = _StubUart()
    p = Pipeline(cfg, _StubInfer(), uart, tmp_path / "h.db")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert len(detections) == 1
    assert p.dispatch_status == "ROI OFF"
    assert uart.sent == []
    assert p.history.query(limit=10) == []
    p.close()


def test_pipeline_outside_roi_renders_but_blocks_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)]
    )
    cfg.roi.x = 300
    cfg.roi.y = 300
    cfg.roi.width = 100
    cfg.roi.height = 100
    uart = _StubUart()
    p = Pipeline(cfg, _StubInfer(), uart, tmp_path / "h.db")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    _arm_dispatch(p)

    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert len(detections) == 1
    assert p.dispatch_status == "outside ROI"
    assert uart.sent == []
    assert p.history.query(limit=10) == []
    p.close()


def test_pipeline_dispatch_cooldown_suppresses_new_tracks(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    uart = _StubUart()
    p = Pipeline(cfg, _SequenceInfer(), uart, tmp_path / "h.db")
    p.set_dispatch_cooldown(60)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    p.process_frame(frame, ts=datetime.now(UTC))
    p.process_frame(frame, ts=datetime.now(UTC))
    p.process_frame(frame, ts=datetime.now(UTC))

    assert [item[1] for item in uart.sent] == ["O"]
    rows = p.history.query(limit=10)
    assert len(rows) == 1
    assert rows[0].uart_command == "O"
    p.close()


def test_pipeline_unknown_object_does_not_dispatch_while_visible(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.model.conf_threshold = 0.4
    cfg.unknown_fallback.stable_frames = 2
    uart = _StubUart()
    p = Pipeline(cfg, _LowConfidencePenInfer(), uart, tmp_path / "h.db")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    for _ in range(6):
        p.process_frame(frame, ts=datetime.now(UTC))
    for _ in range(6):
        p.process_frame(frame, ts=datetime.now(UTC))

    assert uart.sent == []
    assert p.history.query(limit=10) == []
    assert p.dispatch_status == "unknown object review required"
    p.close()


def test_pipeline_blocks_unmapped_out_of_taxonomy_label(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    uart = _StubUart()
    p = Pipeline(cfg, _OutOfTaxonomyInfer(), uart, tmp_path / "h.db")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    p.process_frame(frame, ts=datetime.now(UTC))

    assert uart.sent == []
    assert p.history.query(limit=1) == []
    assert p.dispatch_status == "unknown object review required"
    p.close()


def test_pipeline_allows_out_of_taxonomy_label_with_explicit_mapping(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Mystery gadget", command="R", bin_index=2)]
    )
    uart = _StubUart()
    p = Pipeline(cfg, _OutOfTaxonomyInfer(), uart, tmp_path / "h.db")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    p.process_frame(frame, ts=datetime.now(UTC))

    assert uart.sent == [(1, "R", 0.9)]
    row = p.history.query(limit=1)[0]
    assert row.cls_name == "Mystery gadget"
    assert row.uart_command == "R"
    assert row.bin_index == 2
    p.close()


def test_pipeline_accepts_specialist_class_threshold_below_global_threshold(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.model.conf_threshold = 0.4
    p = Pipeline(cfg, _SpecialistPenInfer(), _StubUart(), tmp_path / "h.db")
    p.set_hardware_dispatch_enabled(False)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert [d.cls_name for d in detections] == ["Pen"]
    assert detections[0].source == YOLO_SPECIALIST_SOURCE
    assert p.uart.sent == []
    p.close()


def test_pipeline_detects_low_conf_unknown_object_without_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.model.conf_threshold = 0.4
    cfg.unknown_fallback.stable_frames = 2
    p = Pipeline(cfg, _LowConfidencePenInfer(), _StubUart(), tmp_path / "h.db")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    first = p.process_frame(frame, ts=datetime.now(UTC))
    second = p.process_frame(frame, ts=datetime.now(UTC))

    assert first == []
    assert len(second) == 1
    assert second[0].cls_name == "Unknown object"
    assert p.uart.sent == []
    assert p.history.query(limit=1) == []
    assert p.dispatch_status == "unknown object review required"
    p.close()


def test_pipeline_dispatches_unknown_only_with_explicit_mapping(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Unknown object", command="R", bin_index=2)]
    )
    cfg.model.conf_threshold = 0.4
    cfg.unknown_fallback.stable_frames = 2
    p = Pipeline(cfg, _LowConfidencePenInfer(), _StubUart(), tmp_path / "h.db")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    p.process_frame(frame, ts=datetime.now(UTC))
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert len(detections) == 1
    assert detections[0].cls_name == "Unknown object"
    assert p.uart.sent == [(1, "R", detections[0].conf)]
    row = p.history.query(limit=1)[0]
    assert row.cls_name == "Unknown object"
    assert row.uart_command == "R"
    assert row.bin_index == 2
    p.close()


def test_pipeline_detects_unknown_when_yolo_returns_no_boxes_without_dispatch(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.unknown_fallback.warmup_frames = 1
    cfg.unknown_fallback.stable_frames = 2
    p = Pipeline(cfg, _NoDetectionInfer(), _StubUart(), tmp_path / "h.db")
    blank = np.full((240, 320, 3), 240, dtype=np.uint8)
    with_object = blank.copy()
    with_object[90:130, 80:220] = 20

    p.process_frame(blank, ts=datetime.now(UTC))
    first = p.process_frame(with_object, ts=datetime.now(UTC))
    second = p.process_frame(with_object, ts=datetime.now(UTC))
    after_removal = [p.process_frame(blank, ts=datetime.now(UTC)) for _ in range(3)]

    assert first == []
    assert len(second) == 1
    assert second[0].cls_name == "Unknown object"
    assert after_removal == [[], [], []]
    assert p.uart.sent == []
    assert p.history.query(limit=1) == []
    assert p.dispatch_status == "waiting empty tray"
    p.close()


def test_pipeline_records_to_history(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)]
    )
    p = Pipeline(cfg, _StubInfer(), _StubUart(), tmp_path / "h.db")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    _arm_dispatch(p)
    p.process_frame(frame, ts=datetime.now(UTC))
    rows = p.history.query(limit=10)
    assert len(rows) == 1
    assert rows[0].cls_name == "paper"
    assert rows[0].image_path
    assert rows[0].annotated_path
    assert rows[0].route_label
    assert rows[0].bin_index == 3
    p.close()


def test_pipeline_saves_labeled_image_before_uart_dispatch(tmp_path, monkeypatch):
    appdata = tmp_path / "appdata"
    monkeypatch.setenv("APPDATA", str(appdata))

    class CheckingUart(_StubUart):
        def send(self, track_id, command, conf):
            assert list((appdata / "TrashSorter" / "detection_captures").rglob("*-labeled.jpg"))
            assert list((appdata / "TrashSorter" / "detection_captures").rglob("*.json"))
            super().send(track_id, command, conf)

    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="paper", command="R", bin_index=2)]
    )
    p = Pipeline(cfg, _StubInfer(), CheckingUart(), tmp_path / "h.db")
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    _arm_dispatch(p)
    p.process_frame(frame, ts=datetime.now(UTC))

    rows = p.history.query(limit=10)
    assert rows[0].uart_command == "I"
    assert Path(rows[0].annotated_path).exists()
    assert Path(rows[0].meta_path).exists()
    p.close()


def test_pipeline_blocks_uart_when_labeled_capture_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="paper", command="R", bin_index=2)]
    )
    uart = _StubUart()
    speaker = _StubSpeaker()
    p = Pipeline(cfg, _StubInfer(), uart, tmp_path / "h.db", speaker=speaker)
    monkeypatch.setattr(
        p,
        "_save_labeled_capture",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    _arm_dispatch(p)
    p.process_frame(frame, ts=datetime.now(UTC))

    rows = p.history.query(limit=10)
    assert len(rows) == 1
    assert rows[0].ack_status == "capture_failed"
    assert rows[0].route_label == "Tái chế"
    assert rows[0].bin_index == 3
    assert uart.sent == []
    assert speaker.spoken == []
    p.close()


def test_pipeline_runs_with_no_uart_worker(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)]
    )
    p = Pipeline(cfg, _StubInfer(), None, tmp_path / "h.db")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert len(detections) == 1
    rows = p.history.query(limit=10)
    assert len(rows) == 1
    assert rows[0].uart_command == "I"
    assert rows[0].bin_index == 3
    assert rows[0].ack_status == "uart_off"
    p.close()


def test_pipeline_does_not_pc_speak_when_uart_off(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)]
    )
    cfg.speaker.output_mode = "computer_speaker"
    cfg.speaker.enabled = True
    speaker = _StubSpeaker()
    p = Pipeline(cfg, _StubInfer(), None, tmp_path / "h.db", speaker=speaker)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    p.process_frame(frame, ts=datetime.now(UTC))

    assert speaker.spoken == []
    assert p.history.query(limit=1)[0].ack_status == "uart_off"
    p.close()
