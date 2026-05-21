import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication

from app.core.config import AppConfig, ClassMapping
from app.ui.controller import AppController


@pytest.fixture
def ctl(qtbot):
    cfg = AppConfig(mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)])
    with tempfile.TemporaryDirectory() as td:
        c = AppController(cfg, Path(td) / "cfg.json", Path(td) / "h.db")
        yield c


def _wait(cond, timeout=2.0):
    import time

    deadline = time.time() + timeout
    while not cond() and time.time() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.02)


def test_test_camera_emits_failure_for_bad_source(ctl):
    results = []
    ctl.test_camera_result.connect(lambda ok, msg: results.append((ok, msg)))
    ctl.test_camera("nonexistent_dev_99")
    _wait(lambda: bool(results), 3.0)
    assert results
    assert results[0][0] is False


def test_test_uart_emits_failure_for_bad_port(ctl):
    results = []
    ctl.test_uart_result.connect(lambda ok, msg: results.append((ok, msg)))
    ctl.test_uart_ping("COM_NOT_REAL", 9600)
    _wait(lambda: bool(results), 3.0)
    assert results
    assert results[0][0] is False


def test_reload_model_emits_failure_for_bad_path(ctl):
    results = []
    ctl.reload_model_result.connect(lambda ok, msg: results.append((ok, msg)))
    ctl.reload_model("does_not_exist.pt")
    _wait(lambda: bool(results), 3.0)
    assert results
    assert results[0][0] is False
