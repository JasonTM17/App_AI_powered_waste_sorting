import json
import os
from pathlib import Path

import cv2
import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QPushButton

from app.core.config import AppConfig, ClassMapping
from app.core.dataset_catalog import DatasetCatalog
from app.core.waste_categories import default_class_id_for_name
from app.ui.pages.capture import CapturePage
from app.ui.widgets.camera_annotation_dialog import CameraAnnotationDialog


def _make_queue_item(
    root: Path,
    stem: str = "manual_abc",
    *,
    source: str = "manual_import",
    cls_id: int = 18,
    cls_name: str = "Paper",
    conf: float = 1.0,
    reviewed: bool | None = None,
) -> Path:
    qdir = root / "low_conf_queue"
    qdir.mkdir(parents=True, exist_ok=True)
    img = np.full((24, 32, 3), 120, dtype=np.uint8)
    img_path = qdir / f"{stem}.jpg"
    cv2.imwrite(str(img_path), img)
    meta = {
        "ts": "2026-05-22T08:00:00",
        "source": source,
        "boxes": [
            {
                "cls_id": cls_id,
                "cls_name": cls_name,
                "conf": conf,
                "xyxy": [0, 0, 32, 24],
            }
        ],
    }
    if reviewed is not None:
        meta["reviewed"] = reviewed
    img_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
    return img_path


def _config_for_dataset(dataset_root: Path) -> AppConfig:
    cfg = AppConfig(mappings=[ClassMapping(class_name="Paper", command="P", bin_index=1)])
    cfg.capture.output_dir = str(dataset_root)
    return cfg


def test_capture_page_warns_when_catalog_is_out_of_sync(tmp_path, qtbot):
    dataset_root = tmp_path / "dataset"
    _make_queue_item(dataset_root)
    page = CapturePage(_config_for_dataset(dataset_root))
    page._catalog_path = tmp_path / "dataset.db"
    qtbot.addWidget(page)

    page.reload()

    text = page.stats.text()
    assert "CSDL: 0" in text
    assert "lệch" in text


def test_capture_page_does_not_load_yolo_model_for_class_selector(tmp_path, qtbot, monkeypatch):
    dataset_root = tmp_path / "dataset"

    def fail_if_model_loaded(*_args, **_kwargs):
        raise AssertionError("YOLO model must not load while constructing CapturePage")

    monkeypatch.setattr("app.ui.pages.capture._cached_model_class_ids", fail_if_model_loaded)
    page = CapturePage(_config_for_dataset(dataset_root))
    qtbot.addWidget(page)

    assert page.class_id_for_name("Textile") == default_class_id_for_name("Textile")


def test_capture_page_syncs_catalog(tmp_path, qtbot):
    dataset_root = tmp_path / "dataset"
    _make_queue_item(dataset_root)
    page = CapturePage(_config_for_dataset(dataset_root))
    page._catalog_path = tmp_path / "dataset.db"
    qtbot.addWidget(page)

    page._sync_catalog()
    qtbot.waitUntil(lambda: page._sync_thread is None, timeout=5000)

    catalog = DatasetCatalog(tmp_path / "dataset.db")
    try:
        assert catalog.count_total() == 1
        assert catalog.count_by_source() == {"manual_import": 1}
    finally:
        catalog.close()
    assert "Đã đồng bộ 1" in page.counter.text()


def test_capture_page_prioritizes_trusted_items_and_marks_pending_items(tmp_path, qtbot):
    dataset_root = tmp_path / "dataset"
    manual = _make_queue_item(
        dataset_root,
        stem="manual_ok",
        source="manual_import",
        cls_id=18,
        cls_name="Paper",
        conf=1.0,
        reviewed=True,
    )
    pending = _make_queue_item(
        dataset_root,
        stem="auto_pending",
        source="auto_low_conf",
        cls_id=1,
        cls_name="Aluminum can",
        conf=0.42,
        reviewed=False,
    )
    catalog = DatasetCatalog(tmp_path / "dataset.db")
    try:
        catalog.upsert_item(manual, json.loads(manual.with_suffix(".json").read_text(encoding="utf-8")))
        catalog.upsert_item(
            pending, json.loads(pending.with_suffix(".json").read_text(encoding="utf-8"))
        )
    finally:
        catalog.close()

    page = CapturePage(_config_for_dataset(dataset_root))
    page._catalog_path = tmp_path / "dataset.db"
    qtbot.addWidget(page)

    page.reload()

    first = page.grid.item(0).text()
    texts = [page.grid.item(i).text() for i in range(page.grid.count())]
    assert "Paper 1.00" in first
    assert any("Cần duyệt" in text for text in texts)


def test_capture_page_marks_hard_negative_as_not_trainable(tmp_path, qtbot):
    dataset_root = tmp_path / "dataset"
    negative = _make_queue_item(
        dataset_root,
        stem="hand_negative",
        source="hard_negative",
        cls_id=0,
        cls_name="Unknown object",
        conf=1.0,
        reviewed=True,
    )
    meta = json.loads(negative.with_suffix(".json").read_text(encoding="utf-8"))
    meta["hard_negative"] = True
    negative.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
    catalog = DatasetCatalog(tmp_path / "dataset.db")
    try:
        catalog.upsert_item(negative, meta)
    finally:
        catalog.close()

    page = CapturePage(_config_for_dataset(dataset_root))
    page._catalog_path = tmp_path / "dataset.db"
    qtbot.addWidget(page)

    page.reload()

    assert page.grid.count() == 1
    assert "Hard negative" in page.grid.item(0).text()


def test_capture_page_does_not_expose_manual_training_controls(tmp_path, qtbot):
    dataset_root = tmp_path / "dataset"
    page = CapturePage(_config_for_dataset(dataset_root))
    qtbot.addWidget(page)
    button_texts = {btn.text() for btn in page.findChildren(QPushButton)}

    assert not any("Thêm ảnh thủ công" in text for text in button_texts)
    assert not any("Chụp & gắn nhãn" in text for text in button_texts)
    assert not any("Train nhanh" in text for text in button_texts)
    assert not any("Train mạnh" in text for text in button_texts)
    assert not hasattr(page, "learn_now_status_requested")
    assert not hasattr(page, "training_status_requested")


def test_camera_annotation_dialog_returns_bbox_and_pending_mode(qtbot):
    frame = np.full((80, 120, 3), 200, dtype=np.uint8)
    dialog = CameraAnnotationDialog(
        frame,
        class_name="Textile",
        initial_bbox=(10, 12, 90, 70),
    )
    qtbot.addWidget(dialog)

    assert dialog.bbox_xyxy() == (10, 12, 90, 70)
    dialog.canvas.set_bbox_xyxy((20, 10, 110, 75))
    dialog._accept_pending()

    assert dialog.approve_now() is False
    assert dialog.bbox_xyxy() == (20, 10, 110, 75)
