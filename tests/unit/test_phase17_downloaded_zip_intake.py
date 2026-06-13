from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.core.dataset_queue import is_trainable_meta, save_item_annotations
from app.core.downloaded_zip_intake import (
    DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE,
    audit_downloaded_zip,
    import_camera_anchor_zip_pending,
    map_vietnam_waste50_alias,
)
from app.core.waste_categories import category_for_class
from app.core.weak_eval_audit import source_anchor_counts
from scripts.export_camera_anchor_recovery_trainset import main as export_camera_anchor_main


def test_phase17_audit_reports_full_image_warning(tmp_path: Path):
    zip_path = _write_camera_anchor_zip(tmp_path)

    report = audit_downloaded_zip(zip_path)

    assert report["sha256"]
    assert report["image_count"] == 1
    assert report["manifest_rows"] == 1
    assert "weak_full_image_bbox_needs_manual_review" in report["warnings"]
    assert "zip_uses_local_5_class_ids_not_project_45" in report["warnings"]


def test_phase17_import_keeps_downloaded_zip_pending_and_not_trainable(tmp_path: Path):
    zip_path = _write_camera_anchor_zip(tmp_path)
    queue = tmp_path / "queue"

    report = import_camera_anchor_zip_pending(zip_path, queue, catalog_path=tmp_path / "dataset.db")

    assert report["imported"] == 1
    meta_path = next(queue.glob("*.json"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["source"] == DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE
    assert meta["reviewed"] is False
    assert meta["needs_annotation"] is True
    assert meta["training_excluded"] is True
    assert meta["recognition_enabled"] is False
    assert meta["real_anchor"] is False
    assert not is_trainable_meta(meta)


def test_phase17_review_unlocks_train_support_but_not_reference(tmp_path: Path):
    zip_path = _write_camera_anchor_zip(tmp_path)
    queue = tmp_path / "queue"
    catalog = tmp_path / "dataset.db"
    import_camera_anchor_zip_pending(zip_path, queue, catalog_path=catalog)
    image_path = next(queue.glob("*.jpg"))

    changed = save_item_annotations(
        image_path.stem,
        [{"cls_id": 42, "cls_name": "Pen", "conf": 1.0, "xyxy": [10, 10, 80, 70]}],
        catalog_path=catalog,
    )

    meta = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert changed == 1
    assert meta["reviewed"] is True
    assert meta["needs_annotation"] is False
    assert meta["training_excluded"] is False
    assert meta["split"] == "train"
    assert meta["recognition_enabled"] is False


def test_phase17_downloaded_bootstrap_does_not_count_real_anchor():
    rows = [
        {
            "source": DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE,
            "split": "train",
            "classes": ["Ceramic"],
        }
    ]

    counts = source_anchor_counts(rows, ("Ceramic",))

    assert counts["Ceramic"]["real_anchor"] == 0
    assert counts["Ceramic"]["missing_real_anchor"] == 25
    assert counts["Ceramic"][f"source:{DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE}"] == 1


def test_phase17_export_forces_downloaded_support_train_and_keeps_anchor_gap(tmp_path, monkeypatch):
    queue = tmp_path / "queue"
    out = tmp_path / "out"
    queue.mkdir()
    _write_item(queue, "downloaded", "Ceramic", DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE, reviewed=True)
    _write_item(queue, "camera", "Ceramic", "manual_camera_capture", reviewed=True)

    monkeypatch.setattr(
        "sys.argv",
        [
            "export_camera_anchor_recovery_trainset.py",
            "--queue",
            str(queue),
            "--out",
            str(out),
            "--max-images",
            "10",
        ],
    )

    assert export_camera_anchor_main() == 0
    report = json.loads((out / "export_report.json").read_text(encoding="utf-8"))

    assert report["images"] == 2
    assert report["camera_anchor_stage"]["anchor_counts"]["Ceramic"]["real_anchor"] == 1
    assert report["camera_anchor_stage"]["missing_anchor_targets"]["Ceramic"] == 24
    assert (out / "labels" / "train" / "downloaded.txt").exists()
    assert (out / "labels" / "valid" / "camera.txt").exists()


def test_phase17_vietnam50_aliases_route_to_45_class_and_bin():
    assert map_vietnam_waste50_alias("foam_box") == "Disposable tableware"
    assert map_vietnam_waste50_alias("ceramic_broken") == "Ceramic"
    assert map_vietnam_waste50_alias("small_electronics") == "Electronics"
    assert map_vietnam_waste50_alias("medicine_blister") == "Unknown plastic"

    assert category_for_class(map_vietnam_waste50_alias("foam_box")).code == "I"
    for alias in ("ceramic_broken", "small_electronics", "medicine_blister"):
        assert category_for_class(map_vietnam_waste50_alias(alias)).code == "R"


def _write_camera_anchor_zip(tmp_path: Path) -> Path:
    zip_path = tmp_path / "camera_anchor_recovery_dataset_v1.zip"
    image_bytes = _image_bytes()
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("class_map.json", json.dumps({"Pen": 0}))
        zf.writestr("yolo_weak/data.yaml", "nc: 1\nnames:\n  0: Pen\n")
        zf.writestr(
            "manifest.csv",
            "file,class,class_id_in_this_zip,label_type\n"
            "raw_images_by_class/Pen/pen_001.jpg,Pen,0,weak_full_image_bbox_needs_manual_review\n",
        )
        zf.writestr(
            "sources.csv",
            "class,image_url,source_page_url,license,author,source_type\n"
            "Pen,https://example.test/pen.jpg,https://example.test/pen,CC BY-SA 4.0,Example,wikimedia\n",
        )
        zf.writestr("raw_images_by_class/Pen/pen_001.jpg", image_bytes)
        zf.writestr("yolo_weak/labels/train/pen_001.txt", "0 0.5 0.5 1.0 1.0\n")
    return zip_path


def _image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (100, 80), (240, 240, 240)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _write_item(queue: Path, name: str, cls_name: str, source: str, *, reviewed: bool) -> None:
    image_path = queue / f"{name}.jpg"
    Image.new("RGB", (100, 80), (240, 240, 240)).save(image_path)
    meta = {
        "source": source,
        "reviewed": reviewed,
        "bbox_reviewed": reviewed,
        "needs_annotation": False,
        "training_excluded": False,
        "canonical_class": cls_name,
        "source_type": "wikimedia",
        "source_url": f"https://example.test/{name}.jpg",
        "source_page_url": f"https://example.test/page/{name}",
        "source_license": "CC BY-SA 4.0",
        "license": "CC BY-SA 4.0",
        "source_author": "Example",
        "boxes": [{"cls_id": 5, "cls_name": cls_name, "conf": 1.0, "xyxy": [10, 10, 80, 70]}],
    }
    image_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
