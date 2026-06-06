import json

import numpy as np
from PIL import Image

from app.core.dataset_queue import import_manual_camera_frame
from scripts.export_yolo_trainset import _export_queue


def test_export_queue_skips_unknown_label_boxes(tmp_path):
    queue = tmp_path / "queue"
    out = tmp_path / "out"
    queue.mkdir()
    image_path = queue / "sample.jpg"
    Image.new("RGB", (100, 100), "white").save(image_path)
    image_path.with_suffix(".json").write_text(
        json.dumps(
            {
                "source": "manual_import",
                "boxes": [
                    {"cls_id": 0, "cls_name": "Known", "xyxy": [10, 10, 50, 50]},
                    {"cls_id": 99, "cls_name": "Mystery", "xyxy": [1, 1, 10, 10]},
                ],
            }
        ),
        encoding="utf-8",
    )

    stats = _export_queue(
        queue,
        out,
        {0: "Known"},
        train_ratio=1.0,
        valid_ratio=0.0,
    )

    label = (out / "labels" / "train" / "sample.txt").read_text(encoding="utf-8")
    assert label.startswith("0 ")
    assert "99 " not in label
    assert stats["skipped_unknown_boxes"] == 1


def test_export_queue_remaps_known_name_to_model_class_id(tmp_path):
    queue = tmp_path / "queue"
    out = tmp_path / "out"
    queue.mkdir()
    image_path = queue / "sample.jpg"
    Image.new("RGB", (100, 100), "white").save(image_path)
    image_path.with_suffix(".json").write_text(
        json.dumps(
            {
                "source": "manual_import",
                "boxes": [
                    {"cls_id": 18, "cls_name": "Paper bag", "xyxy": [10, 10, 50, 50]},
                ],
            }
        ),
        encoding="utf-8",
    )

    stats = _export_queue(
        queue,
        out,
        {18: "Paper", 19: "Paper bag"},
        train_ratio=1.0,
        valid_ratio=0.0,
    )

    label = (out / "labels" / "train" / "sample.txt").read_text(encoding="utf-8")
    assert label.startswith("19 ")
    assert stats["remapped_boxes"] == 1


def test_export_queue_appends_allowed_pen_class(tmp_path):
    queue = tmp_path / "queue"
    out = tmp_path / "out"
    queue.mkdir()
    image_path = queue / "pen.jpg"
    Image.new("RGB", (100, 100), "white").save(image_path)
    image_path.with_suffix(".json").write_text(
        json.dumps(
            {
                "source": "manual_import",
                "boxes": [
                    {"cls_id": 99, "cls_name": "Pen", "xyxy": [10, 10, 90, 50]},
                ],
            }
        ),
        encoding="utf-8",
    )

    stats = _export_queue(
        queue,
        out,
        {0: "Known"},
        train_ratio=1.0,
        valid_ratio=0.0,
    )

    label = (out / "labels" / "train" / "pen.txt").read_text(encoding="utf-8")
    yaml = (out / "data.yaml").read_text(encoding="utf-8")
    assert label.startswith("1 ")
    assert "1: Pen" in yaml
    assert stats["classes"]["Pen"] == 1
    assert stats["remapped_boxes"] == 1


def test_export_queue_maps_common_vietnam_waste_alias_into_fixed_taxonomy(tmp_path):
    queue = tmp_path / "queue"
    out = tmp_path / "out"
    queue.mkdir()
    image_path = queue / "foam_box.jpg"
    Image.new("RGB", (100, 100), "white").save(image_path)
    image_path.with_suffix(".json").write_text(
        json.dumps(
            {
                "source": "manual_import",
                "boxes": [
                    {"cls_id": 99, "cls_name": "Foam food box", "xyxy": [10, 10, 90, 80]},
                ],
            }
        ),
        encoding="utf-8",
    )

    stats = _export_queue(
        queue,
        out,
        {0: "Known"},
        train_ratio=1.0,
        valid_ratio=0.0,
    )

    label = (out / "labels" / "train" / "foam_box.txt").read_text(encoding="utf-8")
    yaml = (out / "data.yaml").read_text(encoding="utf-8")
    assert label.startswith("1 ")
    assert "1: Disposable tableware" in yaml
    assert stats["classes"]["Disposable tableware"] == 1


def test_manual_camera_capture_requires_review_before_export(tmp_path):
    queue = tmp_path / "queue"
    out = tmp_path / "out"
    frame = np.zeros((64, 80, 3), dtype=np.uint8)
    img_path = import_manual_camera_frame(frame, queue, "Pen", 42)

    stats = _export_queue(
        queue,
        out,
        {0: "Known"},
        train_ratio=1.0,
        valid_ratio=0.0,
    )

    assert stats["images"] == 0
    assert stats["skipped_untrusted"] == 1

    meta_path = img_path.with_suffix(".json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["reviewed"] = True
    meta.pop("needs_annotation", None)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    stats = _export_queue(
        queue,
        out,
        {0: "Known"},
        train_ratio=1.0,
        valid_ratio=0.0,
    )

    assert stats["classes"]["Pen"] == 1
