import json
from pathlib import Path

from app.core.dataset_catalog import DatasetCatalog
from app.core.dataset_metadata_migrations import backfill_legacy_camera_bbox_reviews


def _write_meta(path: Path, **overrides) -> None:
    meta = {
        "source": "manual_camera_capture",
        "reviewed": True,
        "reviewed_at": "2026-06-01T10:00:00",
        "needs_annotation": False,
        "boxes": [
            {
                "cls_id": 42,
                "cls_name": "Pen",
                "conf": 1.0,
                "xyxy": [1, 2, 30, 40],
            }
        ],
    }
    meta.update(overrides)
    path.write_text(json.dumps(meta), encoding="utf-8")
    path.with_suffix(".jpg").write_bytes(b"not-needed-by-catalog")


def test_legacy_camera_review_migration_is_dry_run_by_default(tmp_path: Path):
    meta_path = tmp_path / "manual_camera_old.json"
    _write_meta(meta_path)

    result = backfill_legacy_camera_bbox_reviews(tmp_path)

    assert result.eligible == (meta_path,)
    assert result.applied == ()
    assert "bbox_reviewed" not in json.loads(meta_path.read_text(encoding="utf-8"))


def test_legacy_camera_review_migration_applies_and_updates_catalog(tmp_path: Path):
    meta_path = tmp_path / "manual_camera_old.json"
    _write_meta(meta_path)
    db_path = tmp_path / "dataset.db"

    result = backfill_legacy_camera_bbox_reviews(
        tmp_path,
        apply=True,
        catalog_path=db_path,
    )

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert result.applied == (meta_path,)
    assert meta["bbox_reviewed"] is True
    assert meta["recognition_enabled"] is True
    assert meta["metadata_migration"] == "legacy_camera_review_bbox_v1"
    catalog = DatasetCatalog(db_path)
    try:
        item = catalog.get_item("manual_camera_old")
        assert item is not None
        assert item["trust_state"] == "trainable"
    finally:
        catalog.close()


def test_legacy_camera_review_migration_skips_ambiguous_records(tmp_path: Path):
    _write_meta(tmp_path / "manual_camera_pending.json", needs_annotation=True)
    _write_meta(tmp_path / "manual_camera_no_audit.json", reviewed_at="")
    _write_meta(tmp_path / "manual_camera_explicit.json", bbox_reviewed=False)
    _write_meta(tmp_path / "manual_camera_bad_box.json", boxes=[])

    result = backfill_legacy_camera_bbox_reviews(tmp_path, apply=True)

    assert result.eligible == ()
    assert result.applied == ()
