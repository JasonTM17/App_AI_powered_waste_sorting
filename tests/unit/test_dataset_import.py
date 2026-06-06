import json
import zipfile
from pathlib import Path

import cv2
import numpy as np

from app.core.dataset_catalog import DatasetCatalog
from app.utils.dataset_import import import_yolo_dataset_to_queue, label_map_for_preset


def _make_yolo_dataset(root: Path):
    (root / "train" / "images").mkdir(parents=True)
    (root / "train" / "labels").mkdir(parents=True)
    (root / "data.yaml").write_text(
        "train: train/images\nval: train/images\nnames:\n  0: Paper\n  1: Plastic bottle\n",
        encoding="utf-8",
    )
    img = np.full((100, 200, 3), 180, dtype=np.uint8)
    cv2.imwrite(str(root / "train" / "images" / "sample.jpg"), img)
    (root / "train" / "labels" / "sample.txt").write_text(
        "1 0.500000 0.500000 0.250000 0.400000\n",
        encoding="utf-8",
    )


def test_import_yolo_folder_to_queue(tmp_path):
    src = tmp_path / "dataset"
    _make_yolo_dataset(src)
    qdir = tmp_path / "queue"

    catalog_path = tmp_path / "dataset.db"
    n = import_yolo_dataset_to_queue(src, qdir, source_name="roboflow", catalog_path=catalog_path)

    assert n == 1
    jpgs = list(qdir.glob("roboflow_*.jpg"))
    assert len(jpgs) == 1
    meta = json.loads(jpgs[0].with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["source"] == "roboflow"
    assert meta["split"] == "train"
    assert meta["boxes"][0]["cls_name"] == "Plastic bottle"
    assert meta["boxes"][0]["cls_id"] == 1
    assert meta["boxes"][0]["xyxy"] == [75.0, 30.0, 125.0, 70.0]
    catalog = DatasetCatalog(catalog_path)
    try:
        assert catalog.count_total() == 1
        assert catalog.count_by_source() == {"roboflow": 1}
    finally:
        catalog.close()


def test_import_yolo_zip_to_queue(tmp_path):
    src = tmp_path / "dataset"
    _make_yolo_dataset(src)
    zip_path = tmp_path / "dataset.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for p in src.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(src))

    qdir = tmp_path / "queue"
    n = import_yolo_dataset_to_queue(zip_path, qdir, source_name="roboflow")

    assert n == 1
    assert len(list(qdir.glob("roboflow_*.json"))) == 1


def test_import_yolo_remaps_matching_model_class_ids(tmp_path):
    src = tmp_path / "dataset"
    _make_yolo_dataset(src)
    qdir = tmp_path / "queue"

    n = import_yolo_dataset_to_queue(
        src,
        qdir,
        source_name="candidate",
        class_name_to_id={"Paper": 18, "Plastic bottle": 24},
    )

    assert n == 1
    meta = json.loads(next(qdir.glob("candidate_*.json")).read_text(encoding="utf-8"))
    assert meta["source"] == "candidate"
    assert meta["boxes"][0]["cls_name"] == "Plastic bottle"
    assert meta["boxes"][0]["cls_id"] == 24
    assert meta["boxes"][0]["original_cls_id"] == 1


def test_import_yolo_marks_unknown_labels_untrusted(tmp_path):
    src = tmp_path / "dataset"
    _make_yolo_dataset(src)
    qdir = tmp_path / "queue"

    n = import_yolo_dataset_to_queue(
        src,
        qdir,
        source_name="candidate",
        class_name_to_id={"Paper": 18},
    )

    assert n == 1
    meta = json.loads(next(qdir.glob("untrusted_*.json")).read_text(encoding="utf-8"))
    assert meta["source"] == "untrusted"
    assert meta["intended_source"] == "candidate"
    assert meta["unknown_labels"] == ["Plastic bottle"]
    assert meta["boxes"][0]["unknown_label"] is True


def test_import_yolo_label_map_can_trust_known_synonyms(tmp_path):
    src = tmp_path / "dataset"
    _make_yolo_dataset(src)
    qdir = tmp_path / "queue"

    n = import_yolo_dataset_to_queue(
        src,
        qdir,
        source_name="candidate",
        class_name_to_id={"Paper": 18, "Plastic bottle": 24},
        label_map={"Plastic bottle": "Paper"},
    )

    assert n == 1
    meta = json.loads(next(qdir.glob("candidate_*.json")).read_text(encoding="utf-8"))
    assert meta["source"] == "candidate"
    assert meta["boxes"][0]["cls_name"] == "Paper"
    assert meta["boxes"][0]["cls_id"] == 18
    assert meta["boxes"][0]["original_cls_name"] == "Plastic bottle"


def test_import_pen_hardware_download_label_map_and_metadata(tmp_path):
    src = tmp_path / "dataset"
    (src / "train" / "images").mkdir(parents=True)
    (src / "train" / "labels").mkdir(parents=True)
    (src / "data.yaml").write_text(
        "\n".join(
            [
                "train: train/images",
                "val: train/images",
                "nc: 3",
                "names: ['pen', 'battery', 'toothbrushes']",
                "roboflow:",
                "  workspace: the-recyclers-roymu",
                "  project: version2-r1mwb",
                "  version: 1",
                "  license: CC BY 4.0",
                "  url: https://universe.roboflow.com/the-recyclers-roymu/version2-r1mwb/dataset/1",
            ]
        ),
        encoding="utf-8",
    )
    img = np.full((100, 100, 3), 180, dtype=np.uint8)
    cv2.imwrite(str(src / "train" / "images" / "sample.jpg"), img)
    (src / "train" / "labels" / "sample.txt").write_text(
        "0 0.500000 0.500000 0.300000 0.200000\n"
        "1 0.250000 0.250000 0.100000 0.100000\n",
        encoding="utf-8",
    )
    qdir = tmp_path / "queue"

    n = import_yolo_dataset_to_queue(
        src,
        qdir,
        source_name="roboflow_version2",
        class_name_to_id={"Pen": 42, "Battery": 45, "Toothbrush": 46},
        label_map=label_map_for_preset("pen_hardware_downloads"),
    )

    assert n == 1
    meta = json.loads(next(qdir.glob("roboflow_version2_*.json")).read_text(encoding="utf-8"))
    assert meta["source"] == "roboflow_version2"
    assert meta["source_license"] == "CC BY 4.0"
    assert meta["source_project"] == "version2-r1mwb"
    assert meta["source_url"].endswith("/version2-r1mwb/dataset/1")
    assert [box["cls_name"] for box in meta["boxes"]] == ["Pen", "Battery"]
    assert [box["cls_id"] for box in meta["boxes"]] == [42, 45]
    assert "unknown_labels" not in meta
