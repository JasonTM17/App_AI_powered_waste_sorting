import json
import zipfile
from pathlib import Path

import cv2
import numpy as np

from app.core.dataset_catalog import DatasetCatalog
from app.core.kaggle_intake import KAGGLE_MINI_TRASH_VIETNAM_SOURCE
from app.core.waste_categories import TRAINING_CLASS_ORDER_45
from app.core.weak_eval_audit import source_anchor_counts
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


def test_import_yolo_zip_handles_long_roboflow_filenames(tmp_path):
    zip_path = tmp_path / "long.zip"
    image_name = "train/images/" + ("long_roboflow_name_" * 10) + ".jpg"
    label_name = image_name.replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt"
    img = np.full((60, 80, 3), 180, dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", img)
    assert ok
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("data.yaml", "train: train/images\nval: train/images\nnames: ['Can']\n")
        zf.writestr(image_name, encoded.tobytes())
        zf.writestr(label_name, "0 0.500000 0.500000 0.500000 0.500000\n")

    qdir = tmp_path / "queue"
    n = import_yolo_dataset_to_queue(
        zip_path,
        qdir,
        source_name="candidate",
        class_name_to_id={"Aluminum can": 1},
        label_map={"Can": "Aluminum can"},
    )

    assert n == 1
    meta = json.loads(next(qdir.glob("candidate_*.json")).read_text(encoding="utf-8"))
    assert meta["boxes"][0]["cls_name"] == "Aluminum can"


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


def test_import_roboflow_3kelas_maps_clear_labels_and_blocks_plastik(tmp_path):
    src = tmp_path / "dataset"
    (src / "train" / "images").mkdir(parents=True)
    (src / "train" / "labels").mkdir(parents=True)
    (src / "data.yaml").write_text(
        "\n".join(
            [
                "train: train/images",
                "val: train/images",
                "nc: 3",
                "names: ['kertas', 'organik', 'plastik']",
                "roboflow:",
                "  workspace: putric",
                "  project: 3kelas-2zprw",
                "  version: 1",
                "  license: CC BY 4.0",
                "  url: https://universe.roboflow.com/putric/3kelas-2zprw/dataset/1",
            ]
        ),
        encoding="utf-8",
    )
    img = np.full((100, 100, 3), 180, dtype=np.uint8)
    cv2.imwrite(str(src / "train" / "images" / "sample.jpg"), img)
    (src / "train" / "labels" / "sample.txt").write_text(
        "0 0.250000 0.500000 0.200000 0.200000\n"
        "1 0.500000 0.500000 0.200000 0.200000\n"
        "2 0.750000 0.500000 0.200000 0.200000\n",
        encoding="utf-8",
    )

    imported = import_yolo_dataset_to_queue(
        src,
        tmp_path / "queue",
        source_name="roboflow_3kelas_v1",
        class_name_to_id={"Paper": 18, "Organic": 35},
        label_map=label_map_for_preset("roboflow_3kelas_v1"),
    )

    assert imported == 1
    meta = json.loads(next((tmp_path / "queue").glob("untrusted_*.json")).read_text())
    assert meta["source"] == "untrusted"
    assert meta["intended_source"] == "roboflow_3kelas_v1"
    assert meta["unknown_labels"] == ["plastik"]
    assert [box["cls_name"] for box in meta["boxes"]] == ["Paper", "Organic", "plastik"]
    assert [box.get("unknown_label", False) for box in meta["boxes"]] == [False, False, True]
    assert meta["source_license"] == "CC BY 4.0"


def test_import_wastebasket_can_bottle_drops_non_target_labels(tmp_path):
    src = tmp_path / "dataset"
    (src / "train" / "images").mkdir(parents=True)
    (src / "train" / "labels").mkdir(parents=True)
    (src / "data.yaml").write_text(
        "\n".join(
            [
                "train: train/images",
                "val: train/images",
                "nc: 6",
                "names: ['Bottle', 'CAN', 'Dustbin', 'people', 'trashcan', 'pet']",
                "roboflow:",
                "  workspace: asmaa-rashed-alahmari-fvl6d",
                "  project: wastebasket_trash_detecation",
                "  version: 3",
                "  license: Public Domain",
                "  url: https://universe.roboflow.com/asmaa-rashed-alahmari-fvl6d/wastebasket_trash_detecation/dataset/3",
            ]
        ),
        encoding="utf-8",
    )
    img = np.full((100, 100, 3), 180, dtype=np.uint8)
    cv2.imwrite(str(src / "train" / "images" / "sample.jpg"), img)
    (src / "train" / "labels" / "sample.txt").write_text(
        "0 0.200000 0.500000 0.200000 0.200000\n"
        "1 0.400000 0.500000 0.200000 0.200000\n"
        "2 0.600000 0.500000 0.200000 0.200000\n"
        "3 0.700000 0.500000 0.200000 0.200000\n"
        "4 0.800000 0.500000 0.200000 0.200000\n"
        "5 0.900000 0.500000 0.100000 0.200000\n",
        encoding="utf-8",
    )

    imported = import_yolo_dataset_to_queue(
        src,
        tmp_path / "queue",
        source_name="roboflow_wastebasket_can_bottle_v3",
        class_name_to_id={"Aluminum can": 7, "Plastic bottle": 8},
        label_map=label_map_for_preset("roboflow_wastebasket_can_bottle_v3"),
        drop_unmapped_labels=True,
    )

    assert imported == 1
    meta = json.loads(next((tmp_path / "queue").glob("roboflow_wastebasket_can_bottle_v3_*.json")).read_text())
    assert meta["source"] == "roboflow_wastebasket_can_bottle_v3"
    assert meta["source_license"] == "Public Domain"
    assert [box["cls_name"] for box in meta["boxes"]] == [
        "Plastic bottle",
        "Aluminum can",
        "Plastic bottle",
    ]
    assert [box["cls_id"] for box in meta["boxes"]] == [8, 7, 8]
    assert "unknown_labels" not in meta
    assert all("unknown_label" not in box for box in meta["boxes"])


def test_import_kaggle_mini_classes_txt_and_train_support_meta(tmp_path):
    src = tmp_path / "kaggle-mini"
    (src / "images").mkdir(parents=True)
    (src / "labels").mkdir(parents=True)
    (src / "classes.txt").write_text(
        "\n".join(["Foam_box", "Mask", "Metal_can"]),
        encoding="utf-8",
    )
    img = np.full((80, 120, 3), 220, dtype=np.uint8)
    cv2.imwrite(str(src / "images" / "foam.jpg"), img)
    (src / "labels" / "foam.txt").write_text(
        "0 0.500000 0.500000 0.500000 0.500000\n",
        encoding="utf-8",
    )
    class_map = {name: idx for idx, name in enumerate(TRAINING_CLASS_ORDER_45)}

    n = import_yolo_dataset_to_queue(
        src,
        tmp_path / "queue",
        source_name=KAGGLE_MINI_TRASH_VIETNAM_SOURCE,
        class_name_to_id=class_map,
        label_map=label_map_for_preset("kaggle_vietnam_waste"),
        force_split="train",
        extra_meta={
            "source_dataset": "hoaalan/mini-trash-dataset-in-vietnam",
            "source_type": "kaggle_yolo",
            "phase19_kaggle_train_support": True,
            "reviewed": True,
            "needs_annotation": False,
            "split_lock": True,
        },
    )

    assert n == 1
    meta = json.loads(next((tmp_path / "queue").glob("kaggle_mini_trash_vietnam_*.json")).read_text())
    assert meta["source"] == KAGGLE_MINI_TRASH_VIETNAM_SOURCE
    assert meta["split"] == "train"
    assert meta["split_lock"] is True
    assert meta["phase19_kaggle_train_support"] is True
    assert meta["boxes"][0]["cls_name"] == "Disposable tableware"
    assert meta["boxes"][0]["cls_id"] == TRAINING_CLASS_ORDER_45.index("Disposable tableware")


def test_kaggle_vietnam_slug_labels_map_to_45_class_taxonomy(tmp_path):
    src = tmp_path / "garbage-detection-vn"
    (src / "train" / "images").mkdir(parents=True)
    (src / "train" / "labels").mkdir(parents=True)
    (src / "data.yaml").write_text(
        "\n".join(
            [
                "names:",
                "  0: rac-huu-co",
                "  1: chai-nhua",
                "  2: khau-trang",
            ]
        ),
        encoding="utf-8",
    )
    img = np.full((80, 120, 3), 220, dtype=np.uint8)
    cv2.imwrite(str(src / "train" / "images" / "sample.jpg"), img)
    (src / "train" / "labels" / "sample.txt").write_text(
        "0 0.300000 0.300000 0.200000 0.200000\n"
        "1 0.500000 0.500000 0.200000 0.200000\n"
        "2 0.700000 0.700000 0.200000 0.200000\n",
        encoding="utf-8",
    )
    class_map = {name: idx for idx, name in enumerate(TRAINING_CLASS_ORDER_45)}

    n = import_yolo_dataset_to_queue(
        src,
        tmp_path / "queue",
        source_name="kaggle_garbage_detection_vn",
        class_name_to_id=class_map,
        label_map=label_map_for_preset("kaggle_vietnam_waste"),
        force_split="train",
    )

    assert n == 1
    meta = json.loads(next((tmp_path / "queue").glob("kaggle_garbage_detection_vn_*.json")).read_text())
    assert [box["cls_name"] for box in meta["boxes"]] == ["Organic", "Plastic bottle", "Textile"]
    assert [box["cls_id"] for box in meta["boxes"]] == [
        TRAINING_CLASS_ORDER_45.index("Organic"),
        TRAINING_CLASS_ORDER_45.index("Plastic bottle"),
        TRAINING_CLASS_ORDER_45.index("Textile"),
    ]


def test_kaggle_support_source_does_not_count_as_real_anchor():
    counts = source_anchor_counts(
        [
            {
                "source": KAGGLE_MINI_TRASH_VIETNAM_SOURCE,
                "split": "train",
                "classes": ["Disposable tableware"],
            }
        ],
        ("Disposable tableware",),
    )

    assert counts["Disposable tableware"]["real_anchor"] == 0
    assert counts["Disposable tableware"]["source:kaggle_mini_trash_vietnam"] == 1
