import json

from app.core.dataset_queue import (
    _canonical_box_label,
    _clean_box,
    summarize_queue,
)


def test_canonical_box_label():
    name, _i = _canonical_box_label("Pen", 42)
    assert name == "Pen"
    
    # Assuming waste_categories resolves standard IDs correctly, but here we just check fallback
    name2, i2 = _canonical_box_label("Unknown Item", "99")
    assert name2 == "Unknown Item"
    assert i2 == 99


def test_clean_box():
    box = {
        "cls_id": 42,
        "cls_name": "Pen",
        "conf": 0.9,
        "xyxy": [10.0, 20.0, 30.0, 40.0],
    }
    cleaned = _clean_box(box, 100, 100)
    assert cleaned is not None
    assert cleaned["cls_id"] == 42
    assert cleaned["cls_name"] == "Pen"
    assert cleaned["xyxy"] == [10.0, 20.0, 30.0, 40.0]


def test_clean_box_out_of_bounds():
    box = {
        "cls_id": 42,
        "cls_name": "Pen",
        "xyxy": [-10.0, -20.0, 150.0, 150.0],
    }
    cleaned = _clean_box(box, 100, 100)
    assert cleaned is not None
    assert cleaned["xyxy"] == [0.0, 0.0, 100.0, 100.0]


def test_clean_box_invalid():
    # missing xyxy
    box = {"cls_id": 42}
    assert _clean_box(box, 100, 100) is None
    
    # invalid coordinates
    box2 = {"xyxy": [50.0, 50.0, 10.0, 10.0]}
    assert _clean_box(box2, 100, 100) is None


def test_summarize_queue(tmp_path):
    queue_dir = tmp_path / "queue"
    queue_dir.mkdir()
    
    # Missing meta
    img1 = queue_dir / "img1.jpg"
    img1.touch()
    
    # Valid meta
    img2 = queue_dir / "img2.jpg"
    img2.touch()
    meta2 = {
        "source": "manual_import",
        "reviewed": True,
        "bbox_reviewed": True,
        "needs_annotation": False,
        "training_excluded": False,
        "boxes": [{"cls_name": "Pen", "cls_id": 42}]
    }
    img2.with_suffix(".json").write_text(json.dumps(meta2), encoding="utf-8")
    
    # Invalid JSON
    img3 = queue_dir / "img3.jpg"
    img3.touch()
    img3.with_suffix(".json").write_text("{invalid", encoding="utf-8")

    stats = summarize_queue(queue_dir)
    assert stats["images"] == 3
    assert stats["missing_meta"] == 2
    assert "Pen" in stats["classes"]
