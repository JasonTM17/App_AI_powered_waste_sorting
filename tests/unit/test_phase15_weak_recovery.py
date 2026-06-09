from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from app.core.weak_recovery_filters import strict_recovery_allowed
from scripts.audit_weak_recovery_targets import audit_targets
from scripts.export_weak_recovery_v2_trainset import main as export_v2_main


def _write_web_item(
    queue: Path,
    name: str,
    cls_name: str,
    xyxy: list[int],
    *,
    training_excluded: bool = False,
    needs_annotation: bool = False,
    missing_license: bool = False,
) -> None:
    image_path = queue / f"manual_web_{name}.jpg"
    Image.new("RGB", (100, 80), (245, 245, 245)).save(image_path)
    meta = {
        "source": "manual_web_import",
        "source_type": "wikimedia",
        "source_url": f"https://example.test/{name}.jpg",
        "source_page_url": f"https://example.test/page/{name}",
        "source_license": "CC BY-SA 4.0",
        "license": "CC BY-SA 4.0",
        "source_author": "Example",
        "canonical_class": cls_name,
        "reviewed": True,
        "needs_annotation": needs_annotation,
        "training_excluded": training_excluded,
        "boxes": [{"cls_id": 42, "cls_name": cls_name, "conf": 1.0, "xyxy": xyxy}],
    }
    if missing_license:
        meta["source_page_url"] = ""
    image_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")


def test_phase15_strict_filter_rejects_full_image_and_missing_license(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    _write_web_item(queue, "full", "Pen", [0, 0, 100, 80])
    _write_web_item(queue, "missing", "Pen", [10, 10, 80, 60], missing_license=True)
    full_meta = json.loads((queue / "manual_web_full.json").read_text(encoding="utf-8"))
    missing_meta = json.loads((queue / "manual_web_missing.json").read_text(encoding="utf-8"))

    assert strict_recovery_allowed(full_meta, queue / "manual_web_full.jpg")[1] == "whole_image_bbox"
    assert strict_recovery_allowed(missing_meta, queue / "manual_web_missing.jpg")[1] == "missing_web_license"


def test_phase15_export_v2_uses_only_strict_samples(tmp_path, monkeypatch):
    queue = tmp_path / "queue"
    out = tmp_path / "out"
    queue.mkdir()
    _write_web_item(queue, "good", "Pen", [10, 10, 70, 60])
    _write_web_item(queue, "excluded", "Pen", [10, 10, 70, 60], training_excluded=True)
    _write_web_item(queue, "full", "Pen", [0, 0, 100, 80])

    monkeypatch.setattr(
        "sys.argv",
        [
            "export_weak_recovery_v2_trainset.py",
            "--queue",
            str(queue),
            "--out",
            str(out),
            "--max-images",
            "10",
        ],
    )

    assert export_v2_main() == 0
    report = json.loads((out / "export_report.json").read_text(encoding="utf-8"))

    assert report["images"] == 1
    assert report["classes"]["Pen"] == 1
    assert report["strict_stage"]["accepted_images"] == 1
    assert report["strict_stage"]["rejection_reasons"]["not_trainable"] == 1
    assert report["strict_stage"]["rejection_reasons"]["whole_image_bbox"] == 1


def test_phase15_audit_repairs_clear_object_bbox(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    image_path = queue / "manual_web_pen.jpg"
    image = Image.new("RGB", (100, 80), (250, 250, 250))
    for x in range(25, 75):
        for y in range(30, 45):
            image.putpixel((x, y), (20, 80, 220))
    image.save(image_path)
    image_path.with_suffix(".json").write_text(
        json.dumps(
            {
                "source": "manual_web_import",
                "source_type": "wikimedia",
                "source_url": "https://example.test/pen.jpg",
                "source_page_url": "https://example.test/page/pen",
                "source_license": "CC BY-SA 4.0",
                "license": "CC BY-SA 4.0",
                "source_author": "Example",
                "canonical_class": "Pen",
                "reviewed": True,
                "needs_annotation": True,
                "training_excluded": True,
                "boxes": [{"cls_id": 42, "cls_name": "Pen", "conf": 1.0, "xyxy": [0, 0, 100, 80]}],
            }
        ),
        encoding="utf-8",
    )

    report = audit_targets(queue, repair=True, catalog_path=tmp_path / "dataset.db")
    meta = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))

    assert report["repair"]["count"] == 1
    assert meta["training_excluded"] is False
    assert meta["needs_annotation"] is False
    assert meta["phase15_repaired"] is True
    assert meta["boxes"][0]["xyxy"] != [0, 0, 100, 80]


def test_phase15_audit_repairs_pending_web_import(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    image_path = queue / "manual_web_ceramic.jpg"
    image = Image.new("RGB", (100, 80), (248, 248, 248))
    for x in range(35, 68):
        for y in range(22, 60):
            image.putpixel((x, y), (190, 70, 70))
    image.save(image_path)
    image_path.with_suffix(".json").write_text(
        json.dumps(
            {
                "source": "manual_web_import",
                "source_type": "wikimedia",
                "source_url": "https://example.test/ceramic.jpg",
                "source_page_url": "https://example.test/page/ceramic",
                "source_license": "CC BY-SA 4.0",
                "license": "CC BY-SA 4.0",
                "source_author": "Example",
                "canonical_class": "Ceramic",
                "reviewed": False,
                "needs_annotation": True,
                "boxes": [{"cls_id": 37, "cls_name": "Ceramic", "conf": 1.0, "xyxy": [0, 0, 100, 80]}],
            }
        ),
        encoding="utf-8",
    )

    report = audit_targets(queue, repair=True, catalog_path=tmp_path / "dataset.db")
    meta = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))

    assert report["repair"]["count"] == 1
    assert meta["reviewed"] is True
    assert meta["needs_annotation"] is False
    assert meta["training_excluded"] is False
