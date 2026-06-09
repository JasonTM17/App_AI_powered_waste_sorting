import json
import random

from PIL import Image

from app.core.learn_now import build_learn_now_status
from app.core.source_quality_report import build_source_quality_report
from scripts.augment_camera_blur_pack import _augment_queue


def _write_reviewed_item(queue, name: str, cls_name: str = "Pen") -> None:
    image_path = queue / f"{name}.jpg"
    Image.new("RGB", (80, 60), (90, 110, 130)).save(image_path)
    meta = {
        "source": "manual_camera_capture",
        "reviewed": True,
        "split": "train",
        "boxes": [{"cls_id": 42, "cls_name": cls_name, "conf": 1.0, "xyxy": [8, 8, 70, 52]}],
    }
    image_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")


def test_camera_blur_augmentation_is_train_only_and_not_reference(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    _write_reviewed_item(queue, "pen_real")

    created = _augment_queue(queue, tmp_path / "dataset.db", {"Pen"}, 1, 10, random.Random(7))

    assert created == 1
    augmented_meta_path = next(queue.glob("camera_blur_*.json"))
    meta = json.loads(augmented_meta_path.read_text(encoding="utf-8"))
    assert meta["camera_blur_augmented"] is True
    assert meta["source_type"] == "camera_blur_augmented"
    assert meta["recognition_enabled"] is False
    assert meta["split"] == "train"
    assert meta["split_lock"] is True
    assert meta["augmentation_parent"].endswith("pen_real.jpg")

    status = build_learn_now_status(queue, "Pen")["selected"]
    assert status["reviewed_count"] == 2
    assert status["reference_count"] == 1

    quality = build_source_quality_report(queue)
    pen = next(row for row in quality["classes"] if row["class_name"] == "Pen")
    assert quality["augmented_images"] == 1
    assert pen["augmented_count"] == 1
