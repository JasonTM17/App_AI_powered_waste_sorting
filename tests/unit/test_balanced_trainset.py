import json

from PIL import Image

from app.core.balanced_trainset import export_balanced_trainset


def _write_item(queue, name: str, *, holdout: bool) -> None:
    image_path = queue / f"{name}.jpg"
    Image.new("RGB", (100, 60), (40, 40, 40)).save(image_path)
    meta = {
        "source": "manual_camera_capture",
        "reviewed": True,
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
