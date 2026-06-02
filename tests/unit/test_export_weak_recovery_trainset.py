from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from scripts.export_weak_recovery_trainset import main


def _write_item(
    queue: Path,
    name: str,
    cls_name: str,
    *,
    source: str = "manual_web_import",
    training_excluded: bool = False,
    licensed: bool = True,
) -> None:
    image_path = queue / f"{name}.jpg"
    Image.new("RGB", (80, 60), (180, 180, 180)).save(image_path)
    meta = {
        "source": source,
        "reviewed": True,
        "bbox_reviewed": True,
        "training_excluded": training_excluded,
        "boxes": [{"cls_id": 42, "cls_name": cls_name, "conf": 1.0, "xyxy": [5, 5, 70, 50]}],
    }
    if source == "manual_web_import" and licensed:
        meta.update(
            {
                "source_url": f"https://example.test/{name}.jpg",
                "source_license": "manual-test-license",
                "source_author": "test",
                "source_type": "licensed_url",
                "canonical_class": cls_name,
            }
        )
    image_path.with_suffix(".json").write_text(
        json.dumps(meta),
        encoding="utf-8",
    )


def test_weak_recovery_export_skips_training_excluded_and_keeps_45_class_yaml(tmp_path, monkeypatch):
    queue = tmp_path / "queue"
    out = tmp_path / "out"
    queue.mkdir()
    _write_item(queue, "good_pen", "Pen")
    _write_item(queue, "bad_pen", "Pen", training_excluded=True)

    monkeypatch.setattr(
        "sys.argv",
        [
            "export_weak_recovery_trainset.py",
            "--queue",
            str(queue),
            "--out",
            str(out),
            "--max-images",
            "10",
        ],
    )

    assert main() == 0
    report = json.loads((out / "export_report.json").read_text(encoding="utf-8"))
    labels = list((out / "labels").rglob("*.txt"))

    assert report["images"] == 1
    assert report["classes"]["Pen"] == 1
    assert len(labels) == 1
    data_yaml = (out / "data.yaml").read_text(encoding="utf-8")
    assert "nc: 45" in data_yaml


def test_weak_recovery_export_reports_unlicensed_web_import_skip(tmp_path, monkeypatch):
    queue = tmp_path / "queue"
    out = tmp_path / "out"
    queue.mkdir()
    _write_item(queue, "unlicensed_pen", "Pen", licensed=False)

    monkeypatch.setattr(
        "sys.argv",
        [
            "export_weak_recovery_trainset.py",
            "--queue",
            str(queue),
            "--out",
            str(out),
            "--max-images",
            "10",
        ],
    )

    assert main() == 0
    report = json.loads((out / "export_report.json").read_text(encoding="utf-8"))

    assert report["images"] == 0
    assert report["blocked_items"]["source_license_issue"] == 1
    assert report["blocked_items"]["missing_source_license"] == 1
