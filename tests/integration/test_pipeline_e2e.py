import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import numpy as np
from PIL import Image

from app.core.config import AppConfig, ClassMapping
from app.core.events import Detection
from app.core.pipeline import Pipeline
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


class _LowConfidencePenInfer:
    class_names: ClassVar[dict[int, str]] = {42: "Pen"}

    def predict(self, frame):
        return [Detection(42, "Pen", 0.12, (20, 20, 130, 80))]


class _NoDetectionInfer:
    class_names: ClassVar[dict[int, str]] = {}

    def predict(self, frame):
        return []


class _UnknownInfer:
    class_names: ClassVar[dict[int, str]] = {999: "Unknown object"}

    def predict(self, frame):
        return [Detection(999, "Unknown object", 0.39, (15, 12, 65, 28))]


class _StubUart:
    def __init__(self):
        self.sent = []

    def send(self, track_id, command, conf):
        self.sent.append((track_id, command, conf))


class _StubSpeaker:
    def __init__(self):
        self.spoken = []

    def speak(self, *, command, bin_index, cls_name, confidence):
        self.spoken.append((command, bin_index, cls_name, confidence))


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


def _write_manual_reference(
    queue_dir: Path,
    *,
    cls_name: str = "Pen",
    cls_id: int = 42,
    rgb_color: tuple[int, int, int] = (220, 30, 30),
) -> None:
    queue_dir.mkdir(parents=True, exist_ok=True)
    for index in range(3):
        image = Image.new("RGB", (80, 40), (20, 20, 20))
        for x in range(15, 65):
            for y in range(12, 28):
                image.putpixel((x, y), rgb_color)
        img_path = queue_dir / f"manual_camera_ref_{index}.jpg"
        image.save(img_path, format="JPEG", quality=95)
        meta = {
            "source": "manual_camera_capture",
            "reviewed": True,
            "recognition_enabled": True,
            "boxes": [{"cls_id": cls_id, "cls_name": cls_name, "conf": 1.0, "xyxy": [15, 12, 65, 28]}],
        }
        img_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")


def test_pipeline_labels_unknown_with_reviewed_manual_reference(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("TRASH_SORTER_REFERENCE_EMBEDDER", "legacy")
    cfg = _dispatch_ready_config(
        mappings=[ClassMapping(class_name="Pen", command="R", bin_index=2)]
    )
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.model.conf_threshold = 0.3
    cfg.manual_reference_recognition.min_similarity = 0.9
    _write_manual_reference(Path(cfg.capture.output_dir) / "low_conf_queue")
    uart = _StubUart()
    p = Pipeline(cfg, _UnknownInfer(), uart, tmp_path / "h.db")
    p.set_hardware_dispatch_enabled(False)
    frame = np.zeros((40, 80, 3), dtype=np.uint8)
    frame[:, :] = (20, 20, 20)
    frame[12:28, 15:65] = (30, 30, 220)

    detections = p.process_frame(frame, datetime.now(UTC))

    assert [d.cls_name for d in detections] == ["Pen"]
    assert detections[0].conf >= 0.9
    assert uart.sent == []


def test_pipeline_routes_unknown_with_legacy_common_reference_alias(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("TRASH_SORTER_REFERENCE_EMBEDDER", "legacy")
    cfg = _dispatch_ready_config()
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg.model.conf_threshold = 0.3
    cfg.manual_reference_recognition.min_similarity = 0.9
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
    assert speaker.spoken == [("I", 3, "paper", 0.9)]
    row = p.history.query(limit=1)[0]
    assert row.uart_command == "I"
    assert row.bin_index == 3
    p.close()


def test_pipeline_routes_three_representative_classes_to_three_bins(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cfg = _dispatch_ready_config(
        mappings=[
            ClassMapping(class_name="Organic", command="O", bin_index=1),
            ClassMapping(class_name="Plastic bottle", command="R", bin_index=2),
            ClassMapping(class_name="Disposable tableware", command="I", bin_index=3),
        ]
    )
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
        track_id, command, _conf = uart.sent[-1]
        p.on_ack(track_id, command, "ok", 15)

    assert [item[1] for item in uart.sent] == ["O", "I", "R"]
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


def test_pipeline_unknown_object_does_not_loop_while_visible(tmp_path, monkeypatch):
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
    p.on_ack(uart.sent[0][0], uart.sent[0][1], "ok", 12)
    for _ in range(6):
        p.process_frame(frame, ts=datetime.now(UTC))

    assert [item[1] for item in uart.sent] == ["R"]
    assert len(p.history.query(limit=10)) == 1
    p.close()


def test_pipeline_falls_back_for_low_conf_unknown_object(tmp_path, monkeypatch):
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
    assert p.uart.sent == [(1, "R", second[0].conf)]
    row = p.history.query(limit=1)[0]
    assert row.cls_name == "Unknown object"
    assert row.uart_command == "R"
    assert row.bin_index == 2
    p.close()


def test_pipeline_falls_back_when_yolo_returns_no_boxes(tmp_path, monkeypatch):
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

    assert first == []
    assert len(second) == 1
    assert second[0].cls_name == "Unknown object"
    assert p.uart.sent == [(1, "R", second[0].conf)]
    assert p.history.query(limit=1)[0].uart_command == "R"
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
    speaker = _StubSpeaker()
    p = Pipeline(cfg, _StubInfer(), None, tmp_path / "h.db", speaker=speaker)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    _arm_dispatch(p)
    p.process_frame(frame, ts=datetime.now(UTC))

    assert speaker.spoken == []
    assert p.history.query(limit=1)[0].ack_status == "uart_off"
    p.close()
