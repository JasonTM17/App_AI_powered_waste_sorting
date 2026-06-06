import json
import os
from pathlib import Path

import cv2
import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.config import AppConfig, ClassMapping
from app.core.dataset_catalog import DatasetCatalog
from app.ui.pages.capture import CapturePage


def _make_queue_item(root: Path, stem: str = "manual_abc") -> Path:
    qdir = root / "low_conf_queue"
    qdir.mkdir(parents=True, exist_ok=True)
    img = np.full((24, 32, 3), 120, dtype=np.uint8)
    img_path = qdir / f"{stem}.jpg"
    cv2.imwrite(str(img_path), img)
    meta = {
        "ts": "2026-05-22T08:00:00",
        "source": "manual_import",
        "boxes": [
            {
                "cls_id": 18,
                "cls_name": "Paper",
                "conf": 1.0,
                "xyxy": [0, 0, 32, 24],
            }
        ],
    }
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
