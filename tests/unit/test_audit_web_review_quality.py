from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from app.core.dataset_catalog import DatasetCatalog
from app.core.dataset_queue import is_trainable_meta
from scripts.audit_web_review_quality import audit_web_reviews


def _write_web_item(
    queue: Path,
    name: str,
    cls_name: str,
    xyxy: list[int],
    *,
    review_method: str = "phase12_assisted_review",
) -> None:
    image_path = queue / f"manual_web_{name}.jpg"
    Image.new("RGB", (100, 80), (230, 230, 230)).save(image_path)
    image_path.with_suffix(".json").write_text(
        json.dumps(
            {
                "source": "manual_web_import",
                "source_type": "wikimedia",
                "source_url": f"https://example.test/{name}.jpg",
                "source_page_url": f"https://example.test/page/{name}",
                "source_license": "CC BY-SA 4.0",
                "license": "CC BY-SA 4.0",
                "source_author": "Example",
                "canonical_class": cls_name,
                "reviewed": True,
                "needs_annotation": False,
                "review_method": review_method,
                "generated": False,
                "boxes": [{"cls_id": 0, "cls_name": cls_name, "conf": 1.0, "xyxy": xyxy}],
            }
        ),
        encoding="utf-8",
    )


def test_web_audit_flags_whole_image_assisted_review(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    _write_web_item(queue, "pen_full", "Pen", [0, 0, 100, 80])
    _write_web_item(queue, "pen_box", "Pen", [10, 10, 70, 50])

    report = audit_web_reviews(queue, coverage_threshold=0.92)

    assert report["totals"]["reviewed_web"] == 2
    assert report["totals"]["whole_image_bbox"] == 1
    assert report["totals"]["flagged"] == 1
    assert report["classes"]["Pen"]["flagged"] == 1
    assert report["flagged_samples"][0]["max_bbox_coverage"] == 1.0


def test_web_audit_quarantine_excludes_train_and_preserves_source(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    catalog_path = tmp_path / "dataset.db"
    _write_web_item(queue, "battery_full", "Battery", [0, 0, 100, 80])
    catalog = DatasetCatalog(catalog_path)
    try:
        catalog.index_queue(queue)
    finally:
        catalog.close()

    report = audit_web_reviews(queue, quarantine=True, catalog_path=catalog_path)
    meta = json.loads((queue / "manual_web_battery_full.json").read_text(encoding="utf-8"))

    assert report["totals"]["quarantined"] == 1
    assert meta["training_excluded"] is True
    assert meta["training_exclusion_reason"] == "phase14_whole_image_assisted_web_review"
    assert meta["source_page_url"] == "https://example.test/page/battery_full"
    assert meta["source_author"] == "Example"
    assert is_trainable_meta(meta) is False
    catalog = DatasetCatalog(catalog_path)
    try:
        items, total = catalog.list_items(source="manual_web_import")
        assert total == 1
        assert items[0]["reviewed"] == 1
    finally:
        catalog.close()
