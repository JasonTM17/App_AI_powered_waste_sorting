from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from app.core.kaggle_real_image_pipeline import (
    DOMESTIC_SOLID_WASTE_REF,
    VN_TRASH_CLASSIFICATION_REF,
    iter_classification_rows,
    write_manifest,
)
from app.core.waste_categories import TRAINING_CLASS_ORDER_45
from app.utils.dataset_import import import_yolo_dataset_to_queue, label_map_for_preset


def test_phase20_vn_trash_manifest_maps_to_three_bins(tmp_path: Path):
    root = tmp_path / "vn"
    _write_image(root / "VN_trash_classification" / "Train" / "Alu" / "can.jpg")
    _write_image(root / "VN_trash_classification" / "Test" / "Foam_box" / "foam.jpg")

    rows = list(iter_classification_rows(root, VN_TRASH_CLASSIFICATION_REF))

    assert len(rows) == 2
    by_class = {row.source_class: row for row in rows}
    assert by_class["Alu"].canonical_class == "Aluminum can"
    assert by_class["Alu"].bin_code == "I"
    assert by_class["Foam_box"].canonical_class == "Disposable tableware"
    assert by_class["Foam_box"].bin_code == "I"
    assert by_class["Foam_box"].classifier_split == "test"


def test_phase20_domestic_manifest_maps_ambiguous_classes_to_safe_bins(tmp_path: Path):
    root = tmp_path / "domestic"
    _write_image(root / "211_Food_leftover" / "food.jpg")
    _write_image(root / "313_Hazardous_battery" / "battery.jpg")
    _write_image(root / "333_Other_household" / "other.jpg")

    rows = list(iter_classification_rows(root, DOMESTIC_SOLID_WASTE_REF))

    by_class = {row.source_class: row for row in rows}
    assert by_class["211_Food_leftover"].canonical_class == "Organic"
    assert by_class["211_Food_leftover"].bin_code == "O"
    assert by_class["313_Hazardous_battery"].canonical_class == "Battery"
    assert by_class["313_Hazardous_battery"].bin_code == "R"
    assert by_class["333_Other_household"].canonical_class == "Unknown plastic"
    assert by_class["333_Other_household"].bin_code == "R"


def test_phase20_manifest_writer_preserves_missing_bbox_status(tmp_path: Path):
    root = tmp_path / "vn"
    _write_image(root / "VN_trash_classification" / "Train" / "PET" / "bottle.jpg")
    rows = list(iter_classification_rows(root, VN_TRASH_CLASSIFICATION_REF))
    out = tmp_path / "manifest.jsonl"
    summary = tmp_path / "summary.json"

    report = write_manifest(rows, out, summary)

    line = json.loads(out.read_text(encoding="utf-8").strip())
    assert report["images"] == 1
    assert line["canonical_class"] == "Plastic bottle"
    assert line["bin_code"] == "I"
    assert line["bbox_status"] == "missing"
    assert line["yolo_trainable"] is False


def test_phase20_yolo_import_can_skip_existing_original_files(tmp_path: Path):
    src = tmp_path / "dataset"
    (src / "images").mkdir(parents=True)
    (src / "labels").mkdir(parents=True)
    (src / "classes.txt").write_text("Foam_box\n", encoding="utf-8")
    img_path = src / "images" / "foam.jpg"
    _write_image(img_path)
    (src / "labels" / "foam.txt").write_text("0 0.5 0.5 0.4 0.4\n", encoding="utf-8")
    class_map = {name: idx for idx, name in enumerate(TRAINING_CLASS_ORDER_45)}
    queue = tmp_path / "queue"

    first = import_yolo_dataset_to_queue(
        src,
        queue,
        source_name="kaggle_mini_trash_vietnam",
        class_name_to_id=class_map,
        label_map=label_map_for_preset("kaggle_vietnam_waste"),
    )
    second = import_yolo_dataset_to_queue(
        src,
        queue,
        source_name="kaggle_mini_trash_vietnam",
        class_name_to_id=class_map,
        label_map=label_map_for_preset("kaggle_vietnam_waste"),
        skip_original_files={str(img_path.resolve())},
    )

    assert first == 1
    assert second == 0
    assert len(list(queue.glob("*.jpg"))) == 1


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((40, 60, 3), 210, dtype=np.uint8)
    cv2.imwrite(str(path), image)
