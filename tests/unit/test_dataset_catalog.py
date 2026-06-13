import json
from pathlib import Path

import cv2
import numpy as np

from app.core.dataset_catalog import DatasetCatalog


def _make_item(
    qdir: Path,
    stem: str,
    source: str = "manual_import",
    multi_box=False,
    reviewed=False,
    unknown_labels: list[str] | None = None,
) -> Path:
    qdir.mkdir(parents=True, exist_ok=True)
    img = np.full((24, 32, 3), 120, dtype=np.uint8)
    img_path = qdir / f"{stem}.jpg"
    cv2.imwrite(str(img_path), img)
    meta = {
        "ts": "2026-05-22T08:00:00",
        "source": source,
        "reviewed": reviewed,
        "bbox_reviewed": reviewed,
        "boxes": [
            {
                "cls_id": 18,
                "cls_name": "Paper",
                "conf": 1.0,
                "xyxy": [0, 0, 32, 24],
            },
            *(
                [
                    {
                        "cls_id": 2,
                        "cls_name": "Plastic",
                        "conf": 0.9,
                        "xyxy": [4, 4, 16, 12],
                    }
                ]
                if multi_box
                else []
            ),
        ],
    }
    if unknown_labels:
        meta["unknown_labels"] = unknown_labels
    img_path.with_suffix(".json").write_text(
        json.dumps(meta, indent=2),
        encoding="utf-8",
    )
    return img_path


def test_catalog_indexes_queue_and_counts_sources(tmp_path: Path):
    qdir = tmp_path / "queue"
    _make_item(qdir, "manual_abc", "manual_import")
    _make_item(qdir, "roboflow_def", "roboflow")

    catalog = DatasetCatalog(tmp_path / "dataset.db")
    try:
        assert catalog.index_queue(qdir) == 2
        assert catalog.count_total() == 2
        assert catalog.count_by_source() == {"manual_import": 1, "roboflow": 1}
        assert catalog.count_boxes_total() == 2
        assert catalog.count_box_classes() == {"Paper": 2}
    finally:
        catalog.close()


def test_catalog_delete_by_image_paths(tmp_path: Path):
    qdir = tmp_path / "queue"
    img_path = _make_item(qdir, "manual_abc")

    catalog = DatasetCatalog(tmp_path / "dataset.db")
    try:
        catalog.index_queue(qdir)
        catalog.delete_by_image_paths([img_path])
        assert catalog.count_total() == 0
        assert catalog.count_boxes_total() == 0
    finally:
        catalog.close()


def test_catalog_indexes_all_boxes_for_multi_box_item(tmp_path: Path):
    qdir = tmp_path / "queue"
    _make_item(qdir, "manual_abc", multi_box=True)

    catalog = DatasetCatalog(tmp_path / "dataset.db")
    try:
        assert catalog.index_queue(qdir) == 1
        assert catalog.count_total() == 1
        assert catalog.count_boxes_total() == 2
        assert catalog.count_box_classes() == {"Paper": 1, "Plastic": 1}
        assert catalog.count_distinct_box_classes() == 2
    finally:
        catalog.close()


def test_catalog_lists_items_when_class_is_not_the_first_box(tmp_path: Path):
    qdir = tmp_path / "queue"
    image_path = _make_item(qdir, "manual_multi", multi_box=True, reviewed=True)

    catalog = DatasetCatalog(tmp_path / "dataset.db")
    try:
        catalog.index_queue(qdir)
        rows, total = catalog.list_items_for_box_class("Plastic", limit=80)

        assert total == 1
        assert [row["image_path"] for row in rows] == [str(image_path.resolve())]
        assert catalog.count_trust_states_for_box_class("Plastic") == {"quarantine": 1}
    finally:
        catalog.close()


def test_catalog_class_query_deduplicates_repeated_boxes(tmp_path: Path):
    qdir = tmp_path / "queue"
    image_path = _make_item(qdir, "manual_repeat", reviewed=True)
    meta_path = image_path.with_suffix(".json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["boxes"].append(dict(meta["boxes"][0]))
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    catalog = DatasetCatalog(tmp_path / "dataset.db")
    try:
        catalog.index_queue(qdir)
        rows, total = catalog.list_items_for_box_class("Paper", limit=None)

        assert total == 1
        assert len(rows) == 1
    finally:
        catalog.close()


def test_catalog_sync_removes_stale_items(tmp_path: Path):
    qdir = tmp_path / "queue"
    stale = _make_item(qdir, "manual_old")
    keep = _make_item(qdir, "manual_keep")

    catalog = DatasetCatalog(tmp_path / "dataset.db")
    try:
        assert catalog.index_queue(qdir) == 2
        stale.unlink()
        stale.with_suffix(".json").unlink()
        assert catalog.index_queue(qdir) == 1
        assert catalog.count_total() == 1
        assert catalog.count_boxes_total() == 1
        assert catalog.count_by_source() == {"manual_import": 1}
        assert keep.exists()
    finally:
        catalog.close()


def test_catalog_empty_scan_does_not_wipe_existing_items(tmp_path: Path):
    qdir = tmp_path / "queue"
    _make_item(qdir, "manual_keep")

    catalog = DatasetCatalog(tmp_path / "dataset.db")
    try:
        assert catalog.index_queue(qdir) == 1
        empty_dir = tmp_path / "empty-queue"
        empty_dir.mkdir()

        assert catalog.index_queue(empty_dir) == 0
        assert catalog.count_total() == 1
        assert catalog.count_boxes_total() == 1
        assert catalog.get_item("manual_keep") is not None
    finally:
        catalog.close()


def test_catalog_filters_auto_low_conf_as_needing_review_until_reviewed(tmp_path: Path):
    qdir = tmp_path / "queue"
    _make_item(qdir, "auto_raw", "auto_low_conf", reviewed=False)
    _make_item(qdir, "auto_reviewed", "auto_low_conf", reviewed=True)
    _make_item(qdir, "manual_good", "manual_import")
    _make_item(qdir, "unknown_bad", "unknown")

    catalog = DatasetCatalog(tmp_path / "dataset.db")
    try:
        catalog.index_queue(qdir)
        needs_review, needs_review_total = catalog.list_items(trusted=False)
        trusted, trusted_total = catalog.list_items(trusted=True)

        assert needs_review_total == 2
        assert {row["item_id"] for row in needs_review} == {"auto_raw", "unknown_bad"}
        assert trusted_total == 2
        assert {row["item_id"] for row in trusted} == {"auto_reviewed", "manual_good"}
        assert catalog.count_by_trusted() == {"trainable": 2, "needs_review": 2}
    finally:
        catalog.close()


def test_catalog_filters_unknown_labels_as_untrusted(tmp_path: Path):
    qdir = tmp_path / "queue"
    _make_item(qdir, "roboflow_bad", "roboflow", unknown_labels=["Mystery"])

    catalog = DatasetCatalog(tmp_path / "dataset.db")
    try:
        catalog.index_queue(qdir)
        rows, total = catalog.list_items(trusted=False)
        assert total == 1
        assert rows[0]["trusted"] == 0
    finally:
        catalog.close()
