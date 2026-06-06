import json
from pathlib import Path

import cv2
import numpy as np

from app.core.dataset_catalog import DatasetCatalog
from app.core.dataset_queue import is_trainable_meta
from app.ui.pages.capture import (
    delete_queue_items,
    export_yolo_dataset,
    import_manual_images,
    quarantine_untrusted_items,
    relabel_images,
    summarize_queue,
)


def _make_frame(qdir: Path, uid: str, boxes, *, reviewed=True):
    qdir.mkdir(parents=True, exist_ok=True)
    img = np.full((480, 640, 3), 200, dtype=np.uint8)
    cv2.imwrite(str(qdir / f"{uid}.jpg"), img)
    meta = {
        "ts": "2026-05-21T10:00:00",
        "source": "auto_low_conf",
        "reviewed": reviewed,
        "boxes": boxes,
    }
    (qdir / f"{uid}.json").write_text(json.dumps(meta), encoding="utf-8")


def test_export_writes_data_yaml_and_labels(tmp_path):
    qdir = tmp_path / "queue"
    out = tmp_path / "out"
    _make_frame(
        qdir,
        "abc",
        [
            {"cls_id": 0, "cls_name": "paper", "conf": 0.5, "xyxy": [100, 100, 200, 200]},
        ],
    )
    _make_frame(
        qdir,
        "def",
        [
            {"cls_id": 1, "cls_name": "plastic", "conf": 0.4, "xyxy": [10, 10, 50, 50]},
        ],
    )
    n = export_yolo_dataset(qdir, out)
    assert n == 2
    assert (out / "data.yaml").exists()
    yaml = (out / "data.yaml").read_text(encoding="utf-8")
    assert "paper" in yaml and "plastic" in yaml
    assert (out / "images" / "abc.jpg").exists()
    label_text = (out / "labels" / "abc.txt").read_text(encoding="utf-8")
    parts = label_text.strip().split()
    assert parts[0] == "0"
    cx, _cy, _w, _h = (float(x) for x in parts[1:])
    assert abs(cx - 0.234375) < 0.01
    assert 0 <= cx <= 1


def test_export_handles_empty_queue(tmp_path):
    n = export_yolo_dataset(tmp_path / "missing", tmp_path / "out2")
    assert n == 0
    assert (tmp_path / "out2" / "data.yaml").exists()


def test_manual_import_creates_full_image_box(tmp_path):
    src = tmp_path / "paper.png"
    img = np.full((24, 32, 3), 120, dtype=np.uint8)
    cv2.imwrite(str(src), img)

    qdir = tmp_path / "queue"
    catalog_path = tmp_path / "dataset.db"
    n = import_manual_images([str(src)], qdir, "Paper", 18, catalog_path=catalog_path)

    assert n == 1
    jpgs = list(qdir.glob("manual_*.jpg"))
    assert len(jpgs) == 1
    meta = json.loads(jpgs[0].with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["source"] == "manual_import"
    assert meta["boxes"][0]["cls_name"] == "Paper"
    assert meta["boxes"][0]["cls_id"] == 18
    assert meta["boxes"][0]["xyxy"] == [0, 0, 32, 24]
    catalog = DatasetCatalog(catalog_path)
    try:
        assert catalog.count_total() == 1
        assert catalog.count_by_source() == {"manual_import": 1}
    finally:
        catalog.close()


def test_queue_summary_relabel_and_delete(tmp_path):
    qdir = tmp_path / "queue"
    _make_frame(
        qdir,
        "abc",
        [{"cls_id": 18, "cls_name": "Paper", "conf": 0.6, "xyxy": [0, 0, 10, 10]}],
    )

    summary = summarize_queue(qdir)
    assert summary["images"] == 1
    assert summary["boxes"] == 1
    assert summary["classes"]["Paper"] == 1

    img = qdir / "abc.jpg"
    catalog_path = tmp_path / "dataset.db"
    catalog = DatasetCatalog(catalog_path)
    try:
        catalog.index_queue(qdir)
    finally:
        catalog.close()

    assert relabel_images([img], "Plastic bottle", 24, catalog_path=catalog_path) == 1
    meta = json.loads(img.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["boxes"][0]["cls_name"] == "Plastic bottle"
    assert meta["boxes"][0]["cls_id"] == 24
    assert meta["reviewed"] is True

    assert delete_queue_items([img], catalog_path=catalog_path) == 1
    assert not img.exists()
    assert not img.with_suffix(".json").exists()
    catalog = DatasetCatalog(catalog_path)
    try:
        assert catalog.count_total() == 0
    finally:
        catalog.close()


def test_custom_import_source_counts_as_trusted(tmp_path):
    qdir = tmp_path / "queue"
    _make_frame(
        qdir,
        "candidate",
        [{"cls_id": 24, "cls_name": "Plastic bottle", "conf": 1.0, "xyxy": [0, 0, 10, 10]}],
    )
    meta_path = qdir / "candidate.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["source"] = "taco_candidate"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    summary = summarize_queue(qdir)
    assert summary["untrusted"] == 0
    assert export_yolo_dataset(qdir, tmp_path / "out") == 1


def test_export_skips_auto_low_conf_until_reviewed(tmp_path):
    qdir = tmp_path / "queue"
    _make_frame(
        qdir,
        "raw_auto",
        [{"cls_id": 18, "cls_name": "Paper", "conf": 0.6, "xyxy": [0, 0, 10, 10]}],
        reviewed=False,
    )

    assert export_yolo_dataset(qdir, tmp_path / "out") == 0
    meta = json.loads((qdir / "raw_auto.json").read_text(encoding="utf-8"))
    assert is_trainable_meta(meta) is False


def test_quarantine_moves_untrusted_items(tmp_path):
    qdir = tmp_path / "queue"
    _make_frame(
        qdir,
        "trusted",
        [{"cls_id": 18, "cls_name": "Paper", "conf": 0.6, "xyxy": [0, 0, 10, 10]}],
    )
    img = np.full((480, 640, 3), 200, dtype=np.uint8)
    cv2.imwrite(str(qdir / "unknown.jpg"), img)
    (qdir / "unknown.json").write_text(
        json.dumps({"ts": "2026-05-21T10:00:00", "boxes": []}),
        encoding="utf-8",
    )

    summary = summarize_queue(qdir)
    assert summary["untrusted"] == 1

    assert quarantine_untrusted_items(qdir) == 1
    assert (qdir / "trusted.jpg").exists()
    assert not (qdir / "unknown.jpg").exists()
    assert list((qdir.parent / "quarantine").glob("*/*.jpg"))
