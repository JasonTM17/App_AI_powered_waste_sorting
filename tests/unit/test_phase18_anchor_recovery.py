from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from app.core.downloaded_zip_intake import DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE
from app.core.phase18_anchor_tools import audit_camera_anchor_readiness, review_downloaded_bootstrap
from app.core.weak_eval_audit import PHASE16_ANCHOR_TARGETS
from scripts import build_phase18_wikimedia_manifest


def test_phase18_review_downloaded_bootstrap_unlocks_tight_bbox(tmp_path: Path):
    queue = tmp_path / "queue"
    queue.mkdir()
    image_path = _write_image(queue / "downloaded_anchor_sample.jpg")
    _write_meta(image_path, "Pen", DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE, reviewed=False, excluded=True)

    report = review_downloaded_bootstrap(queue, catalog_path=tmp_path / "dataset.db")

    meta = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert report["reviewed_total"] == 1
    assert meta["reviewed"] is True
    assert meta["needs_annotation"] is False
    assert meta["training_excluded"] is False
    assert meta["recognition_enabled"] is False
    assert meta["split"] == "train"
    assert meta["weak_full_image_bbox"] is False
    assert meta["boxes"][0]["xyxy"] != [0, 0, 120, 90]


def test_phase18_readiness_does_not_count_downloaded_support_as_real_anchor(tmp_path: Path):
    queue = tmp_path / "queue"
    queue.mkdir()
    downloaded = _write_image(queue / "downloaded_anchor_support.jpg")
    real = _write_image(queue / "manual_camera_real.jpg")
    _write_meta(downloaded, "Ceramic", DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE, reviewed=True, excluded=False)
    _write_meta(real, "Ceramic", "manual_camera_capture", reviewed=True, excluded=False)

    report = audit_camera_anchor_readiness(queue)
    row = report["classes"]["Ceramic"]

    assert row["real_anchor"] == 1
    assert row["missing_real_anchor"] == PHASE16_ANCHOR_TARGETS["Ceramic"] - 1
    assert row[f"source:{DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE}"] == 1
    assert report["train_allowed"] is False


def test_phase18_wikimedia_manifest_builder_uses_license_metadata(monkeypatch):
    def fake_rows(class_name, queries, target):
        return [
            {
                "image_url": f"https://upload.wikimedia.org/{class_name}.jpg",
                "source_page_url": f"https://commons.wikimedia.org/wiki/File:{class_name}.jpg",
                "license": "CC BY-SA 4.0",
                "author": "Example",
                "source_type": "wikimedia",
                "canonical_class": class_name,
                "generated": False,
            }
        ][:target]

    monkeypatch.setattr(build_phase18_wikimedia_manifest, "wikimedia_rows_for_queries", fake_rows)

    rows = build_phase18_wikimedia_manifest._build_rows(("Pen",), 1, ())

    assert rows == [
        {
            "image_url": "https://upload.wikimedia.org/Pen.jpg",
            "source_page_url": "https://commons.wikimedia.org/wiki/File:Pen.jpg",
            "license": "CC BY-SA 4.0",
            "author": "Example",
            "source_type": "wikimedia",
            "canonical_class": "Pen",
            "generated": False,
            "phase18_weak_class": True,
            "query_terms": list(build_phase18_wikimedia_manifest.DEFAULT_QUERIES["Pen"]),
        }
    ]


def _write_image(path: Path) -> Path:
    image = Image.new("RGB", (120, 90), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle((28, 20, 92, 70), fill=(40, 80, 190))
    image.save(path)
    return path


def _write_meta(image_path: Path, class_name: str, source: str, *, reviewed: bool, excluded: bool) -> None:
    meta = {
        "source": source,
        "reviewed": reviewed,
        "needs_annotation": not reviewed,
        "training_excluded": excluded,
        "recognition_enabled": False,
        "canonical_class": class_name,
        "source_url": "https://upload.wikimedia.org/example.jpg",
        "source_page_url": "https://commons.wikimedia.org/wiki/File:Example.jpg",
        "source_license": "CC BY-SA 4.0",
        "license": "CC BY-SA 4.0",
        "source_author": "Example",
        "source_type": "wikimedia",
        "boxes": [{"cls_id": 5, "cls_name": class_name, "conf": 1.0, "xyxy": [28, 20, 92, 70]}],
    }
    if source == DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE and not reviewed:
        meta["boxes"][0]["xyxy"] = [0, 0, 120, 90]
        meta["weak_full_image_bbox"] = True
    image_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
