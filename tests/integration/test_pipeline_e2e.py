from datetime import datetime, UTC
from pathlib import Path

import numpy as np

from app.core.config import AppConfig, ClassMapping
from app.core.events import Detection
from app.core.pipeline import Pipeline


class _StubInfer:
    class_names = {0: "paper", 1: "plastic"}

    def __init__(self):
        self._n = 0

    def predict(self, frame):
        self._n += 1
        if self._n <= 3:
            return [Detection(0, "paper", 0.9, (10, 10, 100, 100))]
        return []


class _StubUart:
    def __init__(self):
        self.sent = []

    def send(self, track_id, command, conf):
        self.sent.append((track_id, command, conf))


def test_pipeline_emits_one_command_per_object(tmp_path):
    cfg = AppConfig(mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)])
    p = Pipeline(
        cfg=cfg,
        engine=_StubInfer(),
        uart=_StubUart(),
        history_db=tmp_path / "h.db",
    )
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    for _ in range(3):
        p.process_frame(frame, ts=datetime.now(UTC))
    assert len(p.uart.sent) == 1
    assert p.uart.sent[0][1] == "P"
    p.close()


def test_pipeline_skips_unmapped_class(tmp_path):
    cfg = AppConfig(mappings=[])
    p = Pipeline(cfg, _StubInfer(), _StubUart(), tmp_path / "h.db")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    p.process_frame(frame, ts=datetime.now(UTC))
    assert p.uart.sent == []
    p.close()


def test_pipeline_records_to_history(tmp_path):
    cfg = AppConfig(mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)])
    p = Pipeline(cfg, _StubInfer(), _StubUart(), tmp_path / "h.db")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    p.process_frame(frame, ts=datetime.now(UTC))
    rows = p.history.query(limit=10)
    assert len(rows) == 1
    assert rows[0].cls_name == "paper"
    p.close()
