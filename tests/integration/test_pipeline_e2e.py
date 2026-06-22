import json
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import cv2
import numpy as np
from PIL import Image

from app.core import pipeline as pipeline_module
from app.core.config import MULTI_CLASS_WARNING_TEXT, AppConfig, ClassMapping
from app.core.events import Detection, TrackedDetection
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


class _BatteryInfer:
    class_names: ClassVar[dict[int, str]] = {43: "Battery"}

    def predict(self, frame):
        return [Detection(43, "Battery", 0.91, (30, 30, 150, 100))]


class _LowConfidencePlasticBottleDispatchInfer:
    class_names: ClassVar[dict[int, str]] = {1: "Plastic bottle"}

    def predict(self, frame):
        return [Detection(1, "Plastic bottle", 0.44, (20, 20, 150, 150))]


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


class _UnknownLeafInfer:
    class_names: ClassVar[dict[int, str]] = {999: "Unknown object"}

    def predict(self, frame):
        return [Detection(999, "Unknown object", 0.39, (24, 72, 396, 250))]


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


class _OneObjectManyLabelsInfer:
    class_names: ClassVar[dict[int, str]] = {
        2: "Aluminum can",
        3: "Plastic bottle",
        42: "Pen",
    }

    def predict(self, frame):
        return [
            Detection(42, "Pen", 0.45, (70, 80, 520, 190)),
            Detection(3, "Plastic bottle", 0.36, (46, 68, 542, 210)),
            Detection(2, "Aluminum can", 0.18, (190, 92, 430, 182)),
        ]


class _SameClassPairInfer:
    class_names: ClassVar[dict[int, str]] = {42: "Pen"}

    def predict(self, frame):
        return [
            Detection(42, "Pen", 0.92, (10, 10, 100, 100)),
            Detection(42, "Pen", 0.91, (140, 10, 230, 100)),
        ]


class _FragmentedPenInfer:
    class_names: ClassVar[dict[int, str]] = {42: "Pen"}

    def predict(self, frame):
        return [
            Detection(42, "Pen", 0.86, (266, 189, 548, 257), operator_label="Bút bi"),
            Detection(42, "Pen", 0.91, (836, 197, 1045, 236), operator_label="Bút bi"),
        ]


class _OnePenInfer:
    class_names: ClassVar[dict[int, str]] = {42: "Pen"}

    def predict(self, frame):
        return [Detection(42, "Pen", 0.93, (20, 30, 120, 160))]


class _WidePenInfer:
    class_names: ClassVar[dict[int, str]] = {42: "Pen"}

    def predict(self, frame):
        return [Detection(42, "Pen", 0.93, (20, 20, 285, 205))]


class _LooseMergedObjectInfer:
    class_names: ClassVar[dict[int, str]] = {18: "Paper shavings"}

    def predict(self, frame):
        return [Detection(18, "Paper shavings", 0.09, (0, 20, 620, 440))]


class _SpoonAndPenReferenceRecognizer:
    def __init__(self):
        self.calls = 0

    def classify(self, _frame, detection, **_kwargs):
        self.calls += 1
        center_y = (detection.xyxy[1] + detection.xyxy[3]) / 2
        if center_y < 300:
            return SimpleNamespace(
                cls_id=32,
                cls_name="Iron utensils",
                similarity=0.77,
                operator_label="Muong kim loai",
            )
        return SimpleNamespace(
            cls_id=42,
            cls_name="Pen",
            similarity=0.84,
            operator_label="But bi",
        )


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


class _FullFramePlasticBottleInfer:
    class_names: ClassVar[dict[int, str]] = {22: "Plastic bottle"}

    def predict(self, frame):
        height, width = frame.shape[:2]
        return [Detection(22, "Plastic bottle", 0.92, (2, 2, width - 2, height - 2))]


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
    cfg.dispatch_guard.max_dispatch_bbox_area_ratio = 1.0
    cfg.dispatch_guard.min_dispatch_sharpness = 0
    cfg.dispatch_guard.min_dispatch_confidence = 0.0
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


def _leafy_organic_frame() -> np.ndarray:
    frame = np.full((300, 420, 3), 232, dtype=np.uint8)
    cv2.line(frame, (35, 178), (390, 164), (44, 82, 42), 8)
    for index, x in enumerate(range(58, 370, 32)):
        angle = -22 if index % 2 == 0 else 20
        center_y = 143 if index % 2 == 0 else 197
        color = (38, 94, 48) if index % 3 else (44, 78, 38)
        cv2.ellipse(frame, (x, center_y), (18, 48), angle, 0, 360, color, -1)
        cv2.ellipse(frame, (x + 10, center_y + 2), (8, 36), angle, 0, 360, (52, 112, 58), -1)
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


def test_pipeline_blocks_near_full_frame_detection_before_uart(tmp_path):
    cfg = _dispatch_ready_config()
    cfg.dispatch_guard.max_dispatch_bbox_area_ratio = 0.82
    uart = _StubUart()
    p = Pipeline(cfg, _FullFramePlasticBottleInfer(), uart, tmp_path / "h.db")
    frame = np.full((240, 320, 3), 235, dtype=np.uint8)
    frame[70:170, 45:275] = (35, 85, 170)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [item.cls_name for item in detections] == ["Plastic bottle"]
    assert [item.operator_label for item in detections] == ["Đặt vật gọn trong ROI"]
    assert p.dispatch_status == "object framing invalid"
    assert uart.sent == []
    assert p.history.query(limit=10) == []
    p.close()


def test_pipeline_dispatches_medium_confidence_near_full_frame_object(tmp_path):
    cfg = _dispatch_ready_config()
    cfg.dispatch_guard.min_dispatch_confidence = 0.45
    cfg.dispatch_guard.max_dispatch_bbox_area_ratio = 1.0
    uart = _StubUart()
    infer = _ScriptedInfer(
        [[Detection(1, "Plastic bottle", 0.51, (2, 2, 318, 238))]]
    )
    p = Pipeline(cfg, infer, uart, tmp_path / "h.db")
    frame = np.full((240, 320, 3), 235, dtype=np.uint8)
    frame[70:170, 45:275] = (35, 85, 170)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [(item.cls_name, item.conf) for item in detections] == [
        ("Plastic bottle", 0.51)
    ]
    assert uart.sent == [(1, "I", 0.51)]
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


def test_pipeline_throttles_repeated_manual_reference_log_events(tmp_path, monkeypatch):
    pipeline = Pipeline(AppConfig(), _StubInfer(), None, tmp_path / "h.db")
    pipeline._manual_reference_log_interval_seconds = 2.0
    now = [100.0]
    monkeypatch.setattr(pipeline_module.time, "monotonic", lambda: now[0])

    event = {
        "mode": "correction",
        "source_class": "Glass bottle",
        "target_class": "Iron utensils",
        "source_path": "manual_live_metal_spoon_20260615_7.jpg",
    }

    assert pipeline._should_log_manual_reference(**event) is True
    assert pipeline._should_log_manual_reference(**event) is False
    now[0] += 1.9
    assert pipeline._should_log_manual_reference(**event) is False
    now[0] += 0.2
    assert pipeline._should_log_manual_reference(**event) is True
    assert pipeline._should_log_manual_reference(
        **{**event, "source_class": "Battery"}
    ) is True
    pipeline.close()


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


def test_pipeline_corrects_high_confidence_plastic_bottle_leaf_reference(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("TRASH_SORTER_REFERENCE_EMBEDDER", "legacy")
    cfg = _dispatch_ready_config(
        mappings=[
            ClassMapping(class_name="Plastic bottle", command="I", bin_index=3),
            ClassMapping(class_name="Organic", command="O", bin_index=1),
        ]
    )
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.model.conf_threshold = 0.3
    _write_manual_reference(
        Path(cfg.capture.output_dir) / "low_conf_queue",
        cls_name="Organic",
        cls_id=17,
        rgb_color=(40, 90, 40),
        operator_label="La cay",
        count=4,
    )
    infer = _ScriptedInfer([[Detection(1, "Plastic bottle", 0.82, (15, 12, 65, 28))]])
    uart = _StubUart()
    p = Pipeline(cfg, infer, uart, tmp_path / "h.db")
    frame = np.zeros((40, 80, 3), dtype=np.uint8)
    frame[:, :] = (20, 20, 20)
    frame[12:28, 15:65] = (40, 90, 40)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [(d.cls_name, d.source, d.operator_label) for d in detections] == [
        ("Organic", "manual_reference", "Lá cây")
    ]
    assert uart.sent == [(1, "O", detections[0].conf)]
    rows = p.history.query(limit=1)
    assert rows[0].cls_name == "Organic"
    assert rows[0].uart_command == "O"
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


def test_pipeline_dispatches_new_route_without_repeating_visible_previous_object(tmp_path):
    cfg = _dispatch_ready_config(
        mappings=[
            ClassMapping(class_name="Organic", command="O", bin_index=1),
            ClassMapping(class_name="Pen", command="R", bin_index=2),
        ]
    )
    uart = _StubUart()
    same_box = (30, 30, 250, 170)
    p = Pipeline(
        cfg,
        _ScriptedInfer(
            [
                [Detection(17, "Organic", 0.91, same_box)],
                [Detection(17, "Organic", 0.91, same_box)],
                [Detection(42, "Pen", 0.83, same_box)],
            ]
        ),
        uart,
        tmp_path / "h.db",
    )
    p.reset_dispatch_state(arm_immediately=True)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)

    p.process_frame(frame, datetime.now(UTC))
    first_track, first_command, _ = uart.sent[0]
    p.on_ack(first_track, first_command, "ok", 3200)
    p.process_frame(frame, datetime.now(UTC))
    assert [item[1] for item in uart.sent] == ["O"]

    p.process_frame(frame, datetime.now(UTC))

    assert [item[1] for item in uart.sent] == ["O", "R"]
    p.close()


def test_pipeline_rearms_from_one_verified_empty_frame_before_next_object(tmp_path):
    cfg = _dispatch_ready_config()
    cfg.dispatch_guard.empty_rearm_seconds = 60
    cfg.dispatch_guard.empty_rearm_frames = 60
    uart = _StubUart()
    p = Pipeline(
        cfg,
        _ScriptedInfer(
            [
                [Detection(0, "Organic", 0.92, (180, 160, 700, 620))],
                [Detection(18, "Paper", 0.08, (22, 0, 1250, 719))],
                [Detection(1, "Plastic bottle", 0.91, (180, 160, 900, 680))],
            ]
        ),
        uart,
        tmp_path / "h.db",
    )
    p.reset_dispatch_state(arm_immediately=True)
    object_frame = np.full((720, 1280, 3), 210, dtype=np.uint8)
    object_frame[160:650, 180:900] = (45, 55, 155)
    empty_frame = np.full((720, 1280, 3), 210, dtype=np.uint8)
    empty_frame[:, :80] = 25
    empty_frame[:, -80:] = 25

    p.process_frame(object_frame, datetime.now(UTC))
    first_track, first_command, _ = uart.sent[0]
    p.on_ack(first_track, first_command, "ok", 3200)
    p.process_frame(empty_frame, datetime.now(UTC))
    p.process_frame(object_frame, datetime.now(UTC))

    assert [item[1] for item in uart.sent] == ["O", "I"]
    p.close()


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


def test_pipeline_corrects_wall_charger_mislabeled_as_pen(tmp_path, monkeypatch):
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
        cls_name="Electronics",
        cls_id=9,
        rgb_color=(30, 30, 30),
        operator_label="Cục sạc",
        recognition_only=True,
    )
    uart = _StubUart()
    p = Pipeline(cfg, _ForkAsPenInfer(), uart, tmp_path / "h.db")
    frame = np.full((40, 80, 3), 220, dtype=np.uint8)
    frame[8:36, 5:75] = (30, 30, 30)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [(d.cls_name, d.operator_label, d.source) for d in detections] == [
        ("Electronics", "Cục sạc", "manual_reference")
    ]
    assert uart.sent == [(1, "R", detections[0].conf)]
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


def test_pipeline_corrects_leafy_unknown_before_three_bin_recycle_fallback(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Organic", command="O", bin_index=1)]
    )
    cfg.model.conf_threshold = 0.3
    cfg.three_bin_classifier.enabled = True
    cfg.three_bin_classifier.unknown_only = True
    uart = _StubUart()
    p = Pipeline(cfg, _UnknownLeafInfer(), uart, tmp_path / "h.db")
    p._three_bin_classifier = _StubThreeBinClassifier("I")

    _arm_dispatch(p)
    detections = p.process_frame(_leafy_organic_frame(), datetime.now(UTC))

    assert [(item.cls_name, item.source, item.operator_label) for item in detections] == [
        ("Organic", "visual_correction:leafy_organic", "La cay")
    ]
    assert uart.sent == [(1, "O", detections[0].conf)]
    p.close()


def test_pipeline_corrects_pen_like_unknown_before_three_bin_recycle_fallback(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Pen", command="R", bin_index=2)]
    )
    cfg.model.conf_threshold = 0.3
    cfg.three_bin_classifier.enabled = True
    cfg.three_bin_classifier.unknown_only = True
    infer = _ScriptedInfer([[Detection(999, "Unknown object", 0.74, (18, 106, 404, 216))]])
    uart = _StubUart()
    p = Pipeline(cfg, infer, uart, tmp_path / "h.db")
    p._three_bin_classifier = _StubThreeBinClassifier("I")
    frame = np.full((260, 420, 3), 230, dtype=np.uint8)
    cv2.line(frame, (28, 176), (372, 142), (92, 92, 92), 28)
    cv2.line(frame, (32, 160), (360, 130), (166, 166, 164), 10)
    cv2.rectangle(frame, (86, 158), (160, 190), (210, 70, 20), -1)

    _arm_dispatch(p)
    detections = p.process_frame(frame, datetime.now(UTC))

    assert [(item.cls_name, item.source, item.operator_label) for item in detections] == [
        ("Pen", "visual_correction:pen", "But bi")
    ]
    assert uart.sent == []
    assert p.dispatch_status == "low confidence review required"
    p.close()


def test_pipeline_requires_same_label_stability_before_dispatch(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[
            ClassMapping(class_name="Plastic bottle", command="I", bin_index=3),
            ClassMapping(class_name="Organic", command="O", bin_index=1),
        ]
    )
    cfg.model.conf_threshold = 0.3
    cfg.dispatch_guard.min_stable_frames = 2
    cfg.three_bin_classifier.enabled = True
    cfg.three_bin_classifier.unknown_only = True
    same_box = (24, 72, 396, 250)
    infer = _ScriptedInfer(
        [
            [Detection(3, "Plastic bottle", 0.85, same_box)],
            [Detection(999, "Unknown object", 0.39, same_box)],
            [Detection(999, "Unknown object", 0.39, same_box)],
        ]
    )
    uart = _StubUart()
    p = Pipeline(cfg, infer, uart, tmp_path / "h.db")
    p._three_bin_classifier = _StubThreeBinClassifier("I")
    p.reset_dispatch_state(arm_immediately=True)
    frame = _leafy_organic_frame()

    first = p.process_frame(frame, datetime.now(UTC))
    second = p.process_frame(frame, datetime.now(UTC))

    assert [item.cls_name for item in first] == ["Plastic bottle"]
    assert [(item.cls_name, item.operator_label) for item in second] == [("Organic", "La cay")]
    assert uart.sent == []
    assert p.dispatch_status == "waiting stable"

    third = p.process_frame(frame, datetime.now(UTC))

    assert [(item.cls_name, item.operator_label) for item in third] == [("Organic", "La cay")]
    assert uart.sent == [(1, "O", third[0].conf)]
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


def test_pipeline_rearms_and_dispatches_many_consecutive_stable_objects(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Organic", command="O", bin_index=1)]
    )
    cfg.model.conf_threshold = 0.3
    cfg.dispatch_guard.min_stable_frames = 2
    frames = []
    dispatch_count = 20
    for index in range(dispatch_count):
        x_offset = index * 3
        frames.extend(
            [
                [Detection(0, "Organic", 0.90, (80 + x_offset, 96, 360, 236))],
                [Detection(0, "Organic", 0.91, (42 + x_offset, 82, 410, 270))],
                [Detection(0, "Organic", 0.89, (72 + x_offset, 100, 374, 244))],
                [],
            ]
        )
    uart = _StubUart()
    p = Pipeline(cfg, _ScriptedInfer(frames), uart, tmp_path / "h.db")
    object_frame = _leafy_organic_frame()
    empty_frame = np.full_like(object_frame, 232)
    p.reset_dispatch_state(arm_immediately=True)

    for index in range(dispatch_count):
        first = p.process_frame(object_frame, ts=datetime(2026, 6, 17, 8, index, 0, tzinfo=UTC))
        assert len(first) == 1
        assert len(uart.sent) == index
        assert p.dispatch_status == "waiting stable"

        second = p.process_frame(object_frame, ts=datetime(2026, 6, 17, 8, index, 1, tzinfo=UTC))
        assert len(second) == 1
        assert len(uart.sent) == index + 1
        track_id, command, _conf = uart.sent[-1]
        assert command == "O"
        p.on_ack(track_id, command, "ok", 25)

        p.process_frame(object_frame, ts=datetime(2026, 6, 17, 8, index, 2, tzinfo=UTC))
        assert len(uart.sent) == index + 1
        assert p.dispatch_status == "waiting empty tray"

        p.process_frame(empty_frame, ts=datetime(2026, 6, 17, 8, index, 3, tzinfo=UTC))
        assert p.auto_sort_state == "READY"

    assert [item[1] for item in uart.sent] == ["O"] * dispatch_count
    rows = list(reversed(p.history.query(limit=10)))
    assert [row.uart_command for row in rows] == ["O"] * 10
    assert [row.ack_status for row in rows] == ["ok"] * 10
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


def test_pipeline_collapses_many_labels_on_one_object_without_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Pen", command="R", bin_index=2)]
    )
    cfg.model.conf_threshold = 0.15
    cfg.model.class_thresholds["Pen"] = 0.15
    cfg.manual_reference_recognition.enabled = False
    uart = _WarningUart()
    speaker = _StubSpeaker()
    p = Pipeline(cfg, _OneObjectManyLabelsInfer(), uart, tmp_path / "h.db", speaker=speaker)
    p.set_hardware_dispatch_enabled(False)
    frame = np.full((260, 620, 3), 245, dtype=np.uint8)
    frame[94:174, 78:510] = (35, 80, 170)

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert [item.cls_name for item in detections] == ["Pen"]
    assert p.dispatch_status == "TEST OFF"
    assert uart.audio_tracks == []
    assert speaker.texts == []
    p.close()


def test_pipeline_merges_fragmented_pen_before_multi_object_guard(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Pen", command="R", bin_index=2)]
    )
    cfg.model.conf_threshold = 0.15
    uart = _WarningUart()
    p = Pipeline(cfg, _FragmentedPenInfer(), uart, tmp_path / "h.db")
    p.set_hardware_dispatch_enabled(False)
    frame = np.full((420, 1200, 3), 245, dtype=np.uint8)
    frame[189:257, 266:548] = (35, 80, 170)
    frame[197:236, 836:1045] = (44, 56, 112)

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert len(detections) == 1
    assert detections[0].cls_name == "Pen"
    assert detections[0].operator_label == "Bút bi"
    assert detections[0].xyxy == (266, 189, 1045, 257)
    assert p.dispatch_status == "TEST OFF"
    assert uart.audio_tracks == []
    p.close()


def test_pipeline_keeps_one_pet_bottle_when_neck_is_false_labeled_as_pen(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Plastic bottle", command="I", bin_index=3)]
    )
    cfg.model.class_thresholds["Pen"] = 0.15
    cfg.manual_reference_recognition.enabled = False
    cfg.three_bin_classifier.enabled = False
    uart = _WarningUart()
    p = Pipeline(
        cfg,
        _ScriptedInfer(
            [
                [
                    Detection(1, "Plastic bottle", 0.79, (100, 140, 460, 520)),
                    Detection(42, "Pen", 0.74, (710, 190, 800, 390)),
                ]
            ]
        ),
        uart,
        tmp_path / "h.db",
    )
    p.set_hardware_dispatch_enabled(False)
    frame = np.full((540, 800, 3), 245, dtype=np.uint8)
    frame[200:510, 110:460] = (35, 80, 170)
    frame[190:390, 420:800] = (80, 80, 80)

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert [(item.cls_name, item.xyxy) for item in detections] == [
        ("Plastic bottle", (100, 140, 800, 520))
    ]
    assert p.dispatch_status == "TEST OFF"
    assert uart.audio_tracks == []
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


def test_pipeline_merges_two_fragments_of_one_pen_in_multi_object_display():
    detections = [
        Detection(32, "Iron utensils", 0.78, (0, 26, 582, 283)),
        Detection(42, "Pen", 0.84, (21, 370, 416, 459)),
        Detection(42, "Pen", 0.50, (418, 350, 623, 402)),
    ]

    merged = Pipeline._merge_split_same_label_multi_object_matches(detections)

    assert [(item.cls_name, item.xyxy) for item in merged] == [
        ("Iron utensils", (0, 26, 582, 283)),
        ("Pen", (21, 350, 623, 459)),
    ]


def test_pipeline_blocks_two_foreground_objects_when_yolo_sees_one(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Pen", command="R", bin_index=2)]
    )
    cfg.manual_reference_recognition.enabled = False
    uart = _StubUart()
    speaker = _StubSpeaker()
    p = Pipeline(cfg, _OnePenInfer(), uart, tmp_path / "h.db", speaker=speaker)
    p.set_hardware_dispatch_enabled(False)
    frame = np.full((240, 320, 3), 245, dtype=np.uint8)
    frame[24:164, 24:92] = (35, 35, 35)
    frame[56:200, 160:280] = (210, 85, 35)

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert len(detections) == 2
    assert {item.cls_name for item in detections} == {"Pen", "Unknown object"}
    assert p.dispatch_status == "multiple waste types"
    assert uart.sent == []
    assert p.history.query(limit=10) == []
    assert speaker.texts == []
    p.close()


def test_pipeline_blocks_two_objects_merged_into_one_yolo_box(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Pen", command="R", bin_index=2)]
    )
    cfg.manual_reference_recognition.enabled = False
    p = Pipeline(cfg, _WidePenInfer(), _StubUart(), tmp_path / "h.db", speaker=_StubSpeaker())
    p.set_hardware_dispatch_enabled(False)
    frame = np.full((240, 320, 3), 245, dtype=np.uint8)
    frame[24:164, 24:92] = (35, 35, 35)
    frame[56:200, 160:280] = (210, 85, 35)

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert len(detections) == 2
    assert {item.cls_name for item in detections} == {"Unknown object"}
    assert p.dispatch_status == "multiple waste types"
    assert p.uart.sent == []
    p.close()


def test_pipeline_ignores_single_unmatched_foreground_fragment_for_one_tracked_object():
    decision = SimpleNamespace(
        reference_count=1,
        object_count=2,
        unmatched_foreground_count=1,
    )
    tracked = [
        TrackedDetection(
            track_id=1,
            detection=Detection(32, "Iron utensils", 0.78, (0, 20, 300, 180)),
            stable_frames=3,
            first_seen_ts=0.0,
        )
    ]

    assert Pipeline._foreground_block_is_single_object_noise(decision, tracked) is True


def test_pipeline_splits_loose_yolo_box_into_reviewed_spoon_and_pen(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.manual_reference_recognition.enabled = True
    uart = _StubUart()
    p = Pipeline(cfg, _LooseMergedObjectInfer(), uart, tmp_path / "h.db", speaker=_StubSpeaker())
    recognizer = _SpoonAndPenReferenceRecognizer()
    p._manual_reference_recognizer = recognizer
    p.set_hardware_dispatch_enabled(False)
    frame = np.full((480, 640, 3), 235, dtype=np.uint8)
    cv2.line(frame, (0, 180), (300, 162), (76, 76, 78), 62)
    cv2.ellipse(frame, (405, 155), (105, 82), -5, 0, 360, (62, 62, 64), -1)
    cv2.line(frame, (0, 365), (470, 352), (48, 58, 92), 30)
    cv2.line(frame, (70, 353), (450, 347), (95, 105, 125), 8)

    detections = p.process_frame(frame, ts=datetime.now(UTC))
    repeated = p.process_frame(frame, ts=datetime.now(UTC))

    assert sorted((item.cls_name, item.operator_label) for item in detections) == [
        ("Iron utensils", "Muong kim loai"),
        ("Pen", "But bi"),
    ]
    assert p.dispatch_status == "multiple waste types"
    assert {item.cls_name for item in repeated} == {"Iron utensils", "Pen"}
    assert recognizer.calls == 2
    assert uart.sent == []
    assert p.history.query(limit=10) == []
    p.close()


def test_pipeline_recovers_reviewed_spoon_and_pen_when_yolo_returns_nothing(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.manual_reference_recognition.enabled = True
    uart = _StubUart()
    p = Pipeline(cfg, _NoDetectionInfer(), uart, tmp_path / "h.db", speaker=_StubSpeaker())
    p._manual_reference_recognizer = _SpoonAndPenReferenceRecognizer()
    p.set_hardware_dispatch_enabled(False)
    frame = np.full((480, 640, 3), 235, dtype=np.uint8)
    cv2.line(frame, (0, 180), (300, 162), (76, 76, 78), 62)
    cv2.ellipse(frame, (405, 155), (105, 82), -5, 0, 360, (62, 62, 64), -1)
    cv2.line(frame, (0, 365), (470, 352), (48, 58, 92), 30)

    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert {item.cls_name for item in detections} == {"Iron utensils", "Pen"}
    assert p.dispatch_status == "multiple waste types"
    assert uart.sent == []
    assert p.history.query(limit=10) == []
    p.close()


def test_pipeline_shows_two_generic_objects_without_reviewed_labels(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.manual_reference_recognition.enabled = False
    uart = _StubUart()
    p = Pipeline(cfg, _NoDetectionInfer(), uart, tmp_path / "h.db", speaker=_StubSpeaker())
    p.set_hardware_dispatch_enabled(False)
    frame = np.full((480, 640, 3), 235, dtype=np.uint8)
    frame[70:230, 50:270] = (45, 70, 120)
    frame[320:390, 80:530] = (55, 55, 55)

    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert len(detections) == 2
    assert {item.cls_name for item in detections} == {"Unknown object"}
    assert {item.operator_label for item in detections} == {
        "V\u1eadt 1 - c\u1ea7n t\u00e1ch ri\u00eang",
        "V\u1eadt 2 - c\u1ea7n t\u00e1ch ri\u00eang",
    }
    assert p.dispatch_status == "multiple waste types"
    assert uart.sent == []
    assert p.history.query(limit=10) == []
    p.close()


def test_pipeline_holds_two_object_display_through_short_segmentation_dropout(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.manual_reference_recognition.enabled = False
    p = Pipeline(cfg, _NoDetectionInfer(), _StubUart(), tmp_path / "h.db")
    p.set_hardware_dispatch_enabled(False)
    two_objects = np.full((480, 640, 3), 235, dtype=np.uint8)
    two_objects[70:230, 50:270] = (45, 70, 120)
    two_objects[320:390, 80:530] = (55, 55, 55)
    one_object = np.full((480, 640, 3), 235, dtype=np.uint8)
    one_object[70:230, 50:270] = (45, 70, 120)

    acquired = p.process_frame(two_objects, ts=datetime.now(UTC))
    held = [
        p.process_frame(one_object, ts=datetime.now(UTC))
        for _ in range(p._multi_object_display_hold_limit)
    ]
    released = p.process_frame(one_object, ts=datetime.now(UTC))

    assert len(acquired) == 2
    assert all(len(items) == 2 for items in held)
    assert len(released) == 1
    assert p.uart.sent == []
    assert p.history.query(limit=10) == []
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


def test_pipeline_dispatches_low_conf_visual_metal_utensil(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config()
    cfg.dispatch_guard.min_dispatch_confidence = 0.55
    cfg.model.conf_threshold = 0.4
    cfg.unknown_fallback.stable_frames = 1
    uart = _StubUart()
    p = Pipeline(cfg, _LowConfidencePaperSpoonInfer(), uart, tmp_path / "h.db")

    _arm_dispatch(p)
    detections = p.process_frame(_metal_spoon_frame(), ts=datetime.now(UTC))

    assert [(item.cls_name, item.source) for item in detections] == [
        ("Iron utensils", "visual_correction:metal_utensil")
    ]
    assert uart.sent == [(1, "R", detections[0].conf)]
    p.close()


def test_pipeline_dispatches_low_conf_known_class(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Plastic bottle", command="I", bin_index=3)]
    )
    cfg.dispatch_guard.min_dispatch_confidence = 0.55
    uart = _StubUart()
    p = Pipeline(cfg, _LowConfidencePlasticBottleDispatchInfer(), uart, tmp_path / "h.db")

    _arm_dispatch(p)
    detections = p.process_frame(np.full((240, 320, 3), 245, dtype=np.uint8), ts=datetime.now(UTC))

    assert [(item.cls_name, item.conf) for item in detections] == [("Plastic bottle", 0.44)]
    assert uart.sent == [(1, "I", 0.44)]
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


def test_pipeline_warns_when_one_detector_box_contains_two_visible_objects(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Pen", command="R", bin_index=2)]
    )
    uart = _StubUart()
    p = Pipeline(cfg, _WidePenInfer(), uart, tmp_path / "h.db")
    frame = np.full((240, 320, 3), 245, dtype=np.uint8)
    frame[34:68, 30:282] = (45, 45, 180)
    frame[142:214, 72:238] = (35, 95, 35)

    _arm_dispatch(p)
    detections = p.process_frame(frame, ts=datetime.now(UTC))

    assert detections
    assert all(item.source == "foreground_multi_object" for item in detections)
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


def test_pipeline_dispatches_recognized_pen_from_reference_source(tmp_path):
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Pen", command="R", bin_index=2)]
    )
    uart = _StubUart()
    p = Pipeline(
        cfg,
        _ScriptedInfer(
            [
                [
                    Detection(
                        42,
                        "Pen",
                        0.78,
                        (20, 20, 150, 70),
                        source="manual_reference",
                        operator_label="Bút bi",
                    )
                ]
            ]
        ),
        uart,
        tmp_path / "h.db",
    )
    frame = np.zeros((120, 180, 3), dtype=np.uint8)

    _arm_dispatch(p)
    p.process_frame(frame, ts=datetime.now(UTC))

    assert uart.sent == [(1, "R", 0.78)]
    p.close()


def test_pipeline_battery_requires_explicit_confirmation_before_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Battery", command="I", bin_index=3)]
    )
    uart = _StubUart()
    pipeline = Pipeline(cfg, _BatteryInfer(), uart, tmp_path / "h.db")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(pipeline)
    pipeline.process_frame(frame, datetime.now(UTC))
    pipeline.process_frame(frame, datetime.now(UTC))

    assert uart.sent == []
    assert pipeline.hazardous_warning_active() is True
    assert pipeline.dispatch_status == "pin nguy hại cần xác nhận trước khi đưa vào Vô cơ"
    confirmed, message = pipeline.confirm_hazardous_battery_dispatch()
    assert confirmed is True
    assert "Đã gửi lệnh Vô cơ" in message
    assert uart.sent == [(1, "R", 0.91)]
    pipeline.close()


def test_pipeline_clears_hazardous_banner_when_current_object_is_not_battery(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[
            ClassMapping(class_name="Battery", command="I", bin_index=3),
            ClassMapping(class_name="Iron utensils", command="R", bin_index=2),
        ]
    )
    uart = _StubUart()
    pipeline = Pipeline(
        cfg,
        _ScriptedInfer(
            [
                [Detection(43, "Battery", 0.91, (30, 30, 150, 100))],
                [Detection(43, "Battery", 0.91, (30, 30, 150, 100))],
                [Detection(32, "Iron utensils", 0.78, (30, 30, 260, 120))],
            ]
        ),
        uart,
        tmp_path / "h.db",
    )
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(pipeline)
    pipeline.process_frame(frame, datetime.now(UTC))
    pipeline.process_frame(frame, datetime.now(UTC))
    assert pipeline.hazardous_warning_active() is True

    pipeline.process_frame(frame, datetime.now(UTC))

    assert pipeline.hazardous_warning_active() is False
    pipeline.close()


def test_pipeline_battery_confirmation_dispatches_once_immediately(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Battery", command="I", bin_index=3)]
    )
    uart = _StubUart()
    pipeline = Pipeline(
        cfg,
        _ScriptedInfer(
            [
                [Detection(43, "Battery", 0.91, (30, 30, 150, 100))],
                [Detection(43, "Battery", 0.91, (30, 30, 150, 100))],
                [Detection(43, "Battery", 0.91, (220, 180, 340, 250))],
            ]
        ),
        uart,
        tmp_path / "h.db",
    )
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(pipeline)
    pipeline.process_frame(frame, datetime.now(UTC))
    pipeline.process_frame(frame, datetime.now(UTC))
    confirmed, _message = pipeline.confirm_hazardous_battery_dispatch()
    assert confirmed is True
    assert uart.sent == [(1, "R", 0.91)]

    pipeline.process_frame(frame, datetime.now(UTC))

    assert uart.sent == [(1, "R", 0.91)]
    pipeline.close()


def test_pipeline_visual_battery_unknown_requires_confirmation(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Battery", command="I", bin_index=3)]
    )
    cfg.model.class_thresholds["Unknown object"] = 0.05
    uart = _StubUart()
    pipeline = Pipeline(
        cfg,
        _ScriptedInfer(
            [
                [Detection(-1, "Unknown object", 0.14, (112, 38, 196, 310))],
                [Detection(-1, "Unknown object", 0.14, (112, 38, 196, 310))],
            ]
        ),
        uart,
        tmp_path / "h.db",
    )
    frame = np.full((360, 300, 3), 232, dtype=np.uint8)
    cv2.rectangle(frame, (124, 54), (184, 116), (78, 132, 188), -1)
    cv2.rectangle(frame, (124, 116), (184, 294), (34, 34, 36), -1)
    cv2.rectangle(frame, (138, 146), (172, 238), (224, 224, 218), -1)
    cv2.rectangle(frame, (132, 54), (176, 294), (75, 72, 72), 3)

    _arm_dispatch(pipeline)
    detections = pipeline.process_frame(frame, datetime.now(UTC))
    detections = pipeline.process_frame(frame, datetime.now(UTC))

    assert [(item.cls_name, item.source, item.operator_label) for item in detections] == [
        ("Battery", "visual_correction:battery", "Pin AA/AAA")
    ]
    assert uart.sent == []
    assert pipeline.hazardous_warning_active() is True
    assert pipeline.dispatch_status == "pin nguy hại cần xác nhận trước khi đưa vào Vô cơ"
    pipeline.close()


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


def test_pipeline_uses_consensus_reference_for_low_conf_unknown_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Organic", command="O", bin_index=1)]
    )
    cfg.model.conf_threshold = 0.4
    cfg.unknown_fallback.stable_frames = 1

    class ConsensusRecognizer:
        def __init__(self):
            self.calls = []

        def classify(self, _frame, _detection, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                cls_id=17,
                cls_name="Organic",
                similarity=0.66,
                operator_label="Vo trung",
                image_path="manual_live_eggshell.jpg",
                votes=7,
                margin=1.0,
                backend="test",
            )

    recognizer = ConsensusRecognizer()
    p = Pipeline(cfg, _LowConfidencePenInfer(), _StubUart(), tmp_path / "h.db")
    p._manual_reference_recognizer = recognizer
    p.set_hardware_dispatch_enabled(False)

    detections = p.process_frame(np.zeros((480, 640, 3), dtype=np.uint8), ts=datetime.now(UTC))

    assert [d.cls_name for d in detections] == ["Organic"]
    assert recognizer.calls == [
        {
            "allowed_classes": None,
            "min_similarity": 0.65,
            "min_consensus_similarity": 0.65,
            "min_votes": 4,
        }
    ]
    p.close()


def test_pipeline_blocks_unknown_even_when_a_legacy_mapping_exists(tmp_path, monkeypatch):
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
    assert p.uart.sent == []
    assert p.history.query(limit=1) == []
    assert p.dispatch_status == "unknown object review required"
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
