import json

import numpy as np
from PIL import Image

from app.core.dataset_queue import import_manual_camera_frame, save_reviewed_camera_annotation
from scripts.export_yolo_trainset import _export_queue


def test_export_queue_blocks_item_with_unknown_label_boxes(tmp_path):
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
                    {"cls_id": 18, "cls_name": "Paper", "xyxy": [10, 10, 50, 50]},
                    {"cls_id": 99, "cls_name": "Mystery", "xyxy": [1, 1, 10, 10]},
                ],
            }
        ),
        encoding="utf-8",
    )

    stats = _export_queue(
        queue,
        out,
        {18: "Paper"},
        train_ratio=1.0,
        valid_ratio=0.0,
    )

    assert stats["images"] == 0
    assert stats["skipped_untrusted"] == 1
    assert not (out / "labels" / "train" / "sample.txt").exists()


def test_export_queue_removes_stale_images_labels_and_caches(tmp_path):
    queue = tmp_path / "queue"
    out = tmp_path / "out"
    queue.mkdir()
    stale_image = out / "images" / "train" / "stale.jpg"
    stale_label = out / "labels" / "train" / "stale.txt"
    stale_cache = out / "train.cache"
    stale_image.parent.mkdir(parents=True)
    stale_label.parent.mkdir(parents=True)
    stale_image.write_bytes(b"old")
    stale_label.write_text("0 0.5 0.5 1 1\n", encoding="utf-8")
    stale_cache.write_bytes(b"cache")

    image_path = queue / "sample.jpg"
    Image.new("RGB", (100, 100), "white").save(image_path)
    image_path.with_suffix(".json").write_text(
        json.dumps(
            {
                "source": "manual_import",
                "reviewed": True,
                "bbox_reviewed": True,
                "boxes": [{"cls_id": 18, "cls_name": "Paper", "xyxy": [10, 10, 50, 50]}],
            }
        ),
        encoding="utf-8",
    )

    stats = _export_queue(queue, out, {18: "Paper"}, train_ratio=1.0, valid_ratio=0.0)

    assert stats["images"] == 1
    assert (out / "images" / "train" / "sample.jpg").exists()
    assert not stale_image.exists()
    assert not stale_label.exists()
    assert not stale_cache.exists()


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
    assert stats["class_count"] == 45


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
    assert label.startswith("42 ")
    assert "42: Pen" in yaml
    assert "nc: 45" in yaml
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
    assert label.startswith("8 ")
    assert "8: Disposable tableware" in yaml
    assert "nc: 45" in yaml
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

    assert stats["images"] == 0
    assert stats["skipped_untrusted"] == 1

    meta["bbox_reviewed"] = True
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    stats = _export_queue(
        queue,
        out,
        {0: "Known"},
        train_ratio=1.0,
        valid_ratio=0.0,
    )

    assert stats["classes"]["Pen"] == 1


def test_reviewed_camera_annotation_exports_textile_with_fixed_class_id(tmp_path):
    queue = tmp_path / "queue"
    out = tmp_path / "out"
    frame = np.zeros((64, 80, 3), dtype=np.uint8)
    img_path = save_reviewed_camera_annotation(
        frame,
        queue,
        "miếng vải",
        0,
        [10, 8, 70, 52],
    )

    meta = json.loads(img_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["reviewed"] is True
    assert meta["bbox_reviewed"] is True
    assert meta["needs_annotation"] is False
    assert meta["boxes"][0]["cls_name"] == "Textile"
    assert meta["boxes"][0]["cls_id"] == 37

    stats = _export_queue(
        queue,
        out,
        {0: "Known"},
        train_ratio=1.0,
        valid_ratio=0.0,
    )

    label = (out / "labels" / "train" / f"{img_path.stem}.txt").read_text(encoding="utf-8")
    yaml = (out / "data.yaml").read_text(encoding="utf-8")
    assert label.startswith("37 ")
    assert "37: Textile" in yaml
    assert "nc: 45" in yaml
    assert stats["classes"]["Textile"] == 1


def test_export_queue_skips_holdout_items(tmp_path):
    queue = tmp_path / "queue"
    out = tmp_path / "out"
    queue.mkdir()
    image_path = queue / "holdout.jpg"
    Image.new("RGB", (100, 100), "white").save(image_path)
    image_path.with_suffix(".json").write_text(
        json.dumps(
            {
                "source": "manual_import",
                "holdout": True,
                "split": "test",
                "boxes": [
                    {"cls_id": 18, "cls_name": "Paper", "xyxy": [10, 10, 50, 50]},
                ],
            }
        ),
        encoding="utf-8",
    )

    stats = _export_queue(
        queue,
        out,
        {18: "Paper"},
        train_ratio=1.0,
        valid_ratio=0.0,
    )

    assert stats["images"] == 0
    assert stats["skipped_untrusted"] == 1
