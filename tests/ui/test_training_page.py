import os
import time
from pathlib import Path

import cv2
import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFileDialog, QPushButton

import app.ui.pages.training as training_module
from app.core.config import AppConfig, ClassMapping
from app.ui.pages.training import TrainingPage


def _config_for_dataset(dataset_root: Path) -> AppConfig:
    cfg = AppConfig(mappings=[ClassMapping(class_name="Textile", command="R", bin_index=2)])
    cfg.capture.output_dir = str(dataset_root)
    return cfg


def _set_label(page: TrainingPage, value: str) -> None:
    page.class_select.setCurrentText(value)
    if page.class_select.lineEdit() is not None:
        page.class_select.lineEdit().setText(value)


def test_training_page_defaults_to_pen_and_enables_manual_actions(tmp_path, qtbot):
    page = TrainingPage(_config_for_dataset(tmp_path / "dataset"))
    qtbot.addWidget(page)

    assert page.selected_class_name() == "Pen"
    assert page.btn_add_phone.isEnabled() is True
    assert page.btn_capture_pending.isEnabled() is True
    assert page.btn_annotate.isEnabled() is True
    assert page.btn_learn_refresh.isEnabled() is True
    assert page.btn_train_micro.isEnabled() is False
    assert page.btn_train_strong.isEnabled() is False


def test_training_page_disables_manual_actions_for_invalid_label(tmp_path, qtbot):
    page = TrainingPage(_config_for_dataset(tmp_path / "dataset"))
    qtbot.addWidget(page)

    _set_label(page, "not-a-canonical-class")

    assert page.btn_add_phone.isEnabled() is False
    assert page.btn_capture_pending.isEnabled() is False
    assert page.btn_annotate.isEnabled() is False
    assert page.btn_learn_refresh.isEnabled() is False
    assert "not-a-canonical-class" in page.label_status.text()


def test_training_page_maps_vietnamese_label_to_textile(tmp_path, qtbot):
    page = TrainingPage(_config_for_dataset(tmp_path / "dataset"))
    qtbot.addWidget(page)

    _set_label(page, "vải")

    assert page.selected_class_name() == "Textile"
    assert page.class_id_for_name("vải") == 37
    assert "Textile" in page.label_status.text()


def test_training_page_manual_phone_import_requires_label_and_emits_pending_import(
    tmp_path,
    qtbot,
    monkeypatch,
):
    image_path = tmp_path / "phone.jpg"
    cv2.imwrite(str(image_path), np.full((20, 30, 3), 200, dtype=np.uint8))
    page = TrainingPage(_config_for_dataset(tmp_path / "dataset"))
    qtbot.addWidget(page)
    _set_label(page, "vải")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileNames",
        lambda *_args, **_kwargs: ([str(image_path)], ""),
    )
    button = next(btn for btn in page.findChildren(QPushButton) if btn.text() == "Thêm ảnh thủ công")

    with qtbot.waitSignal(page.manual_phone_import_requested, timeout=500) as blocker:
        button.click()

    assert blocker.args == ["Textile", 37, [str(image_path)]]


def test_training_page_camera_annotation_button_emits_class_and_id(tmp_path, qtbot):
    page = TrainingPage(_config_for_dataset(tmp_path / "dataset"))
    qtbot.addWidget(page)
    _set_label(page, "miếng vải")
    button = next(btn for btn in page.findChildren(QPushButton) if btn.text() == "Chụp & gắn nhãn")

    with qtbot.waitSignal(page.camera_annotation_requested, timeout=500) as blocker:
        button.click()

    assert blocker.args == ["Textile", 37]


def test_training_page_manual_training_panel_gates_buttons(tmp_path, qtbot):
    page = TrainingPage(_config_for_dataset(tmp_path / "dataset"))
    qtbot.addWidget(page)
    _set_label(page, "Textile")

    assert page.btn_train_micro.isEnabled() is False
    assert page.btn_train_strong.isEnabled() is False

    page.set_learn_now_status(
        {
            "selected": {
                "class_name": "Textile",
                "command": "R",
                "bin_index": 2,
                "route_label": "Vô cơ",
                "reviewed_count": 6,
                "eligible_reviewed_count": 6,
                "reference_count": 6,
                "holdout_count": 0,
                "source_issue_count": 0,
                "missing_for_reference": 0,
                "missing_for_micro_train": 0,
                "missing_for_strong_train": 18,
                "missing_holdout_for_strong": 6,
                "ready_for_micro_train": True,
                "ready_for_strong_train": False,
                "message": "Ready for fast candidate micro-train.",
            }
        }
    )
    page.set_training_status({"running": False, "message": "Training đang tắt"})

    assert page.btn_train_micro.isEnabled() is True
    assert page.btn_train_strong.isEnabled() is False
    assert "Textile" in page.learn_route.text()
    assert "Reference: 6/6" in page.learn_counts.text()


def test_training_page_training_running_disables_train_and_enables_stop(tmp_path, qtbot):
    page = TrainingPage(_config_for_dataset(tmp_path / "dataset"))
    qtbot.addWidget(page)
    _set_label(page, "Textile")
    page.set_learn_now_status(
        {
            "selected": {
                "class_name": "Textile",
                "command": "R",
                "bin_index": 2,
                "route_label": "Vô cơ",
                "reviewed_count": 24,
                "eligible_reviewed_count": 24,
                "reference_count": 6,
                "holdout_count": 6,
                "source_issue_count": 0,
                "missing_for_reference": 0,
                "missing_for_micro_train": 0,
                "missing_for_strong_train": 0,
                "missing_holdout_for_strong": 0,
                "ready_for_micro_train": True,
                "ready_for_strong_train": True,
                "message": "Ready for strong candidate training.",
            }
        }
    )

    page.set_training_status(
        {
            "running": True,
            "message": "Đang chạy 1/6",
            "run_name": "learn-now-micro-textile",
            "progress_percent": 15.0,
            "best_model_path": "",
        }
    )

    assert page.btn_train_micro.isEnabled() is False
    assert page.btn_train_strong.isEnabled() is False
    assert page.btn_stop_training.isEnabled() is True
    assert "learn-now-micro-textile" in page.training_status.text()


def test_training_page_reload_returns_before_slow_worker_finishes(tmp_path, qtbot, monkeypatch):
    class DeferredWorker(QThread):
        metadata_ready = Signal(int, object)
        thumbnails_ready = Signal(int, object)
        failed = Signal(int, str)

        def __init__(self, request_id, *_args):
            super().__init__()
            self.request_id = request_id

        def start(self):
            return None

    monkeypatch.setattr(training_module, "_TrainingDataWorker", DeferredWorker)
    page = TrainingPage(_config_for_dataset(tmp_path / "dataset"))
    qtbot.addWidget(page)

    started = time.perf_counter()
    page.reload()
    elapsed = time.perf_counter() - started

    assert elapsed < 0.3
    assert "Đang tải mẫu Pen" in page.stats.text()


def test_training_page_ignores_metadata_from_stale_class_request(tmp_path, qtbot):
    page = TrainingPage(_config_for_dataset(tmp_path / "dataset"))
    qtbot.addWidget(page)
    page._load_request_id = 2
    page.stats.setText("current request")
    stale_payload = {
        "rows": [{"image_path": "old.jpg", "selected_cls_name": "Pen"}],
        "total": 1,
        "counts": {},
    }

    page._on_training_metadata_ready(1, stale_payload)

    assert page.grid.count() == 0
    assert page.stats.text() == "current request"
