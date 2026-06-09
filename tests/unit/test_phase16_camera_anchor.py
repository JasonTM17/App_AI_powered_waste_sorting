from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from app.core.waste_categories import TRAINING_CLASS_ORDER_45
from app.core.weak_eval_audit import (
    class_id_mismatches,
    match_detections,
    source_anchor_counts,
)
from scripts.export_camera_anchor_recovery_trainset import main as export_camera_anchor_main


def test_weak_eval_match_reports_false_negative_and_confusion():
    gts = [{"class_name": "Ceramic", "xyxy": (10.0, 10.0, 60.0, 60.0)}]
    preds = [
        {
            "class_name": "Disposable tableware",
            "xyxy": (12.0, 12.0, 58.0, 58.0),
            "conf": 0.75,
        }
    ]

    report = match_detections(gts, preds, focus_classes={"Ceramic", "Disposable tableware"})

    assert report["counts"]["Ceramic"]["fn"] == 1
    assert report["counts"]["Ceramic"]["confused_as:Disposable tableware"] == 1
    assert report["failures"][0]["kind"] == "false_negative"


def test_phase16_class_id_mismatch_detects_wrong_taxonomy():
    names = {index: name for index, name in enumerate(TRAINING_CLASS_ORDER_45)}
    names[8] = "Wrong class"

    mismatches = class_id_mismatches(names)

    assert mismatches == [
        {"class_id": 8, "expected": "Disposable tableware", "actual": "Wrong class"}
    ]


def test_phase16_source_anchor_counts_reports_missing_real_anchors():
    rows = [
        {"source": "manual_camera_capture", "split": "test", "classes": ["Ceramic"]},
        {"source": "manual_web_import", "split": "train", "classes": ["Ceramic"]},
    ]

    counts = source_anchor_counts(rows, ("Ceramic",))

    assert counts["Ceramic"]["real_anchor"] == 1
    assert counts["Ceramic"]["missing_real_anchor"] == 24
    assert counts["Ceramic"]["source:manual_web_import"] == 1


def test_phase16_export_forces_web_train_and_reports_anchor_gap(tmp_path, monkeypatch):
    queue = tmp_path / "queue"
    out = tmp_path / "out"
    queue.mkdir()
    _write_item(queue, "web", "Disposable tableware", "manual_web_import")
    _write_item(queue, "camera", "Ceramic", "manual_camera_capture")

    monkeypatch.setattr(
        "sys.argv",
        [
            "export_camera_anchor_recovery_trainset.py",
            "--queue",
            str(queue),
            "--out",
            str(out),
            "--max-images",
            "10",
        ],
    )

    assert export_camera_anchor_main() == 0
    report = json.loads((out / "export_report.json").read_text(encoding="utf-8"))

    assert report["images"] == 2
    assert report["camera_anchor_stage"]["anchor_counts"]["Ceramic"]["real_anchor"] == 1
    assert report["camera_anchor_stage"]["missing_anchor_targets"]["Ceramic"] == 24
    assert (out / "labels" / "train" / "web.txt").exists()
    assert (out / "labels" / "valid" / "camera.txt").exists()


def _write_item(queue: Path, name: str, cls_name: str, source: str) -> None:
    image_path = queue / f"{name}.jpg"
    Image.new("RGB", (100, 80), (240, 240, 240)).save(image_path)
    meta = {
        "source": source,
        "reviewed": True,
        "needs_annotation": False,
        "canonical_class": cls_name,
        "source_type": "wikimedia",
        "source_url": f"https://example.test/{name}.jpg",
        "source_page_url": f"https://example.test/page/{name}",
        "source_license": "CC BY-SA 4.0",
        "license": "CC BY-SA 4.0",
        "source_author": "Example",
        "boxes": [{"cls_id": 8, "cls_name": cls_name, "conf": 1.0, "xyxy": [10, 10, 80, 70]}],
    }
    image_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
