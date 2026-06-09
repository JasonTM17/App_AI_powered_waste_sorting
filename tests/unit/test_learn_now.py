import json

from PIL import Image

from app.core.learn_now import build_learn_now_status


def _write_item(queue, name: str, cls_name: str, *, reviewed: bool = True, holdout: bool = False) -> None:
    image_path = queue / f"{name}.jpg"
    Image.new("RGB", (64, 48), (100, 120, 140)).save(image_path)
    meta = {
        "source": "manual_camera_capture",
        "reviewed": reviewed,
        "holdout": holdout,
        "split": "test" if holdout else "train",
        "split_lock": holdout,
        "boxes": [
            {
                "cls_id": 999,
                "cls_name": cls_name,
                "conf": 1.0,
                "xyxy": [4, 4, 60, 44],
            }
        ],
    }
    image_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")


def test_learn_now_counts_reviewed_references_and_routes_pen(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    for index in range(6):
        _write_item(queue, f"pen_{index}", "but bi")

    status = build_learn_now_status(queue, "cay but")
    selected = status["selected"]

    assert selected["class_name"] == "Pen"
    assert selected["class_id"] == 42
    assert selected["command"] == "R"
    assert selected["bin_index"] == 2
    assert selected["reference_count"] == 6
    assert selected["priority"] == "P0"
    assert selected["ready_for_reference"] is True
    assert selected["ready_for_micro_train"] is True


def test_learn_now_micro_and_strong_thresholds(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    for index in range(18):
        _write_item(queue, f"pen_train_{index}", "Pen")
    for index in range(6):
        _write_item(queue, f"pen_holdout_{index}", "Pen", holdout=True)

    status = build_learn_now_status(queue, "Pen")
    selected = status["selected"]

    assert selected["reviewed_count"] == 24
    assert selected["holdout_count"] == 6
    assert selected["ready_for_micro_train"] is True
    assert selected["ready_for_strong_train"] is True
    assert selected["recommended_action"] == "strong_train"


def test_learn_now_blocks_non_contract_labels(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    _write_item(queue, "organic", "vo chuoi")
    _write_item(queue, "unknown_label", "Yoga Mat")

    status = build_learn_now_status(queue, "vo chuoi")
    selected = status["selected"]

    assert selected["class_name"] == "Organic"
    assert selected["command"] == "O"
    assert selected["priority"] == "P1"
    assert status["blocked_labels"] == {"Yoga Mat": 1}


def test_learn_now_generated_images_do_not_count_as_references(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    for index in range(6):
        _write_item(queue, f"generated_pen_{index}", "Pen")
        meta_path = queue / f"generated_pen_{index}.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta.update(
            {
                "generated": True,
                "source_type": "generated",
                "recognition_enabled": False,
                "source_url": "https://example.test/generated.jpg",
                "source_license": "generated-training-only",
                "source_author": "local-generator",
                "canonical_class": "Pen",
            }
        )
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

    selected = build_learn_now_status(queue, "Pen")["selected"]

    assert selected["reviewed_count"] == 6
    assert selected["generated_count"] == 6
    assert selected["reference_count"] == 0
    assert selected["ready_for_reference"] is False


def test_learn_now_excludes_quarantined_web_references(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    for index in range(6):
        _write_item(queue, f"web_pen_{index}", "Pen")
        meta_path = queue / f"web_pen_{index}.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta.update(
            {
                "source": "manual_web_import",
                "reviewed": True,
                "training_excluded": True,
                "recognition_enabled": False,
                "source_url": f"https://example.test/pen_{index}.jpg",
                "source_page_url": f"https://example.test/page/pen_{index}",
                "source_license": "CC BY-SA 4.0",
                "source_author": "Example",
            }
        )
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

    selected = build_learn_now_status(queue, "Pen")["selected"]

    assert selected["reviewed_count"] == 6
    assert selected["trainable_count"] == 0
    assert selected["reference_count"] == 0
    assert selected["ready_for_reference"] is False
