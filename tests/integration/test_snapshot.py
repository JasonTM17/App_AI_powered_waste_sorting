import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication

from app.core.config import AppConfig, ClassMapping
from app.ui.controller import AppController


@pytest.fixture
def ctl(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    cfg = AppConfig(mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)])
    c = AppController(cfg, tmp_path / "cfg.json", tmp_path / "h.db")
    yield c


def _wait(cond, timeout=2.0):
    import time
    deadline = time.time() + timeout
    while not cond() and time.time() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.02)


def test_snapshot_emits_failure_with_no_frame(ctl):
    results = []
    ctl.snapshot_saved.connect(lambda ok, p: results.append((ok, p)))
    ctl.take_snapshot()
    _wait(lambda: bool(results))
    assert results
    assert results[0][0] is False


def test_snapshot_writes_jpg_when_frame_present(ctl):
    ctl._last_frame = np.full((240, 320, 3), 128, dtype=np.uint8)
    results = []
    ctl.snapshot_saved.connect(lambda ok, p: results.append((ok, p)))
    ctl.take_snapshot()
    _wait(lambda: bool(results))
    assert results and results[0][0] is True
    assert Path(results[0][1]).exists()
