import json

from PIL import Image

from app.core.balanced_trainset import export_balanced_trainset


def _write_item(queue, name: str, *, holdout: bool) -> None:
    image_path = queue / f"{name}.jpg"
    Image.new("RGB", (100, 60), (40, 40, 40)).save(image_path)
    meta = {
        "source": "manual_camera_capture",
        "reviewed": True,
        "bbox_reviewed": True,
        "capture_session_id": "session-1",
        "split": "test" if holdout else "train",
        "split_lock": True,
        "holdout": holdout,
        "boxes": [
            {
                "cls_id": 0,
                "cls_name": "Pen",
                "conf": 1.0,
                "xyxy": [10, 10, 90, 40],
            }
        ],
    }
    image_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")


def _write_alias_item(
    queue,
    name: str,
    cls_name: str,
    *,
    generated: bool = False,
    augmented: bool = False,
    split: str = "train",
) -> None:
    image_path = queue / f"{name}.jpg"
    Image.new("RGB", (100, 60), (40, 40, 40)).save(image_path)
    meta = {
        "source": "manual_camera_capture",
        "reviewed": True,
        "bbox_reviewed": True,
        "generated": generated,
        "camera_blur_augmented": augmented,
        "source_type": "generated" if generated else "camera_blur_augmented" if augmented else "camera",
        "recognition_enabled": not generated,
        "augmentation_parent": "parent.jpg" if augmented else "",
        "augmentation_profile": "test_blur" if augmented else "",
        "split": split,
        "split_lock": generated or augmented,
        "boxes": [
            {
                "cls_id": 999,
                "cls_name": cls_name,
                "conf": 1.0,
                "xyxy": [10, 10, 90, 40],
            }
        ],
    }
    image_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")


def test_balanced_export_respects_split_locked_holdout(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    _write_item(queue, "pen_train_1", holdout=False)
    _write_item(queue, "pen_train_2", holdout=False)
    _write_item(queue, "pen_holdout", holdout=True)
    out = tmp_path / "fast"

    stats = export_balanced_trainset(
        queue,
        out,
        ("Pen", "Battery"),
        max_images=10,
        legacy_quota=2,
    )

    assert stats["images"] == 3
    assert len(list((out / "images" / "train").glob("*.jpg"))) == 2
    assert len(list((out / "images" / "test").glob("*.jpg"))) == 1
    assert "nc: 2" in (out / "data.yaml").read_text(encoding="utf-8")


def test_balanced_export_canonicalizes_aliases_and_reports_blocked_labels(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    _write_alias_item(queue, "banana", "vo chuoi")
    _write_alias_item(queue, "blocked", "Yoga Mat")
    out = tmp_path / "fast"

    stats = export_balanced_trainset(
        queue,
        out,
        ("Organic", "Pen"),
        max_images=10,
        legacy_quota=2,
    )

    assert stats["images"] == 1
    assert stats["classes"] == {"Organic": 1}
    assert stats["blocked_labels"] == {"Yoga Mat": 1}
    assert stats["skipped_unknown_boxes"] == 0
    label_file = next((out / "labels").glob("*/*.txt"))
    assert label_file.read_text(encoding="utf-8").startswith("0 ")


def test_balanced_export_caps_generated_and_forces_train_split(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    for index in range(8):
        _write_alias_item(queue, f"real_pen_{index}", "Pen")
    for index in range(4):
        _write_alias_item(queue, f"generated_pen_{index}", "Pen", generated=True, split="test")
    out = tmp_path / "fast"

    stats = export_balanced_trainset(
        queue,
        out,
        ("Pen",),
        max_images=20,
        legacy_quota=20,
        generated_cap_ratio=0.2,
    )

    assert stats["images"] == 10
    assert len(list((out / "images" / "train").glob("generated_*.jpg"))) == 2
    assert not list((out / "images" / "test").glob("generated_*.jpg"))


def test_balanced_export_forces_augmented_to_train_split(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    _write_alias_item(queue, "augmented_pen", "Pen", augmented=True, split="test")
    out = tmp_path / "fast"

    stats = export_balanced_trainset(
        queue,
        out,
        ("Pen",),
        max_images=5,
        legacy_quota=5,
    )

    assert stats["images"] == 1
    assert len(list((out / "images" / "train").glob("augmented_pen.jpg"))) == 1
    assert not list((out / "images" / "test").glob("augmented_pen.jpg"))


def test_balanced_export_purges_stale_ultralytics_cache(tmp_path):
    """Stale .cache files must be removed at the start of every export.

    Regression for "Image Not Found" at YOLO train time: a cached label cache
    references images that no longer exist in the trainset.
    """
    out = tmp_path / "fast"
    out.mkdir()
    (out / "labels.cache").write_text("stale", encoding="utf-8")

    queue = tmp_path / "queue"
    queue.mkdir()
    _write_item(queue, "pen_train", holdout=False)

    export_balanced_trainset(
        queue,
        out,
        ("Pen",),
        max_images=5,
        legacy_quota=2,
    )

    assert not list(out.glob("*.cache"))
