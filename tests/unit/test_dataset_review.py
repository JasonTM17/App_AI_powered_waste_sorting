import json
from pathlib import Path

import pytest
from PIL import Image

from app.core.dataset_catalog import DatasetCatalog
from app.core.dataset_review import (
    DatasetReviewError,
    DatasetReviewRequest,
    apply_dataset_review_action,
)
from app.core.dataset_trust import DatasetTrustState, classify_dataset_item, is_trainable_meta


def _write_item(queue: Path, stem: str, meta: dict) -> Path:
    queue.mkdir(parents=True, exist_ok=True)
    image_path = queue / f"{stem}.jpg"
    Image.new("RGB", (80, 60), (210, 210, 210)).save(image_path)
    image_path.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return image_path


def _meta(source: str = "manual_camera_capture", cls_name: str = "Pen", **extra) -> dict:
    meta = {
        "source": source,
        "reviewed": False,
        "needs_annotation": True,
        "boxes": [{"cls_id": 42, "cls_name": cls_name, "conf": 1.0, "xyxy": [4, 5, 50, 40]}],
    }
    meta.update(extra)
    return meta


def test_approve_records_review_history_and_unblocks_train(tmp_path):
    image_path = _write_item(tmp_path / "queue", "camera", _meta())

    meta = apply_dataset_review_action(
        image_path,
        DatasetReviewRequest(action="approve", actor="admin", reason="bbox checked"),
    )

    assert meta["reviewed"] is True
    assert meta["bbox_reviewed"] is True
    assert meta["needs_annotation"] is False
    assert meta["recognition_enabled"] is True
    assert meta["review_history"][-1]["action"] == "approve"
    assert meta["review_history"][-1]["state_before"] == DatasetTrustState.NEEDS_REVIEW.value
    assert meta["review_history"][-1]["state_after"] == DatasetTrustState.TRAINABLE.value
    assert is_trainable_meta(meta) is True


def test_relabel_canonicalizes_alias_and_updates_catalog(tmp_path):
    queue = tmp_path / "queue"
    image_path = _write_item(queue, "item", _meta(cls_name="Pen"))
    catalog_path = tmp_path / "dataset.db"

    meta = apply_dataset_review_action(
        image_path,
        DatasetReviewRequest(action="relabel", cls_name="hop nhua", actor="admin", reason="plastic box"),
        catalog_path=catalog_path,
    )

    assert meta["boxes"][0]["cls_name"] == "Plastic canister"
    assert meta["boxes"][0]["cls_id"] == 26
    assert meta["previous_class_names"] == ["Pen"]
    catalog = DatasetCatalog(catalog_path)
    try:
        row = catalog.get_item("item")
        assert row is not None
        assert row["cls_name"] == "Plastic canister"
        assert row["trusted"] == 1
    finally:
        catalog.close()


def test_relabel_rejects_off_taxonomy_target(tmp_path):
    image_path = _write_item(tmp_path / "queue", "item", _meta())

    with pytest.raises(DatasetReviewError):
        apply_dataset_review_action(
            image_path,
            DatasetReviewRequest(action="relabel", cls_name="Mystery class", actor="admin"),
        )


def test_quarantine_marks_in_place_without_moving_or_deleting(tmp_path):
    image_path = _write_item(tmp_path / "queue", "bad", _meta(source="manual_import", reviewed=True))
    meta_path = image_path.with_suffix(".json")

    meta = apply_dataset_review_action(
        image_path,
        DatasetReviewRequest(action="quarantine", actor="admin", reason="hand frame"),
    )

    assert image_path.exists()
    assert meta_path.exists()
    assert meta["quarantined"] is True
    assert meta["training_excluded"] is True
    assert meta["quarantine_reason"] == "hand frame"
    assert classify_dataset_item(meta).state is DatasetTrustState.QUARANTINE


def test_hard_negative_clears_boxes_and_blocks_train(tmp_path):
    image_path = _write_item(tmp_path / "queue", "negative", _meta())

    meta = apply_dataset_review_action(
        image_path,
        DatasetReviewRequest(action="hard_negative", actor="admin", reason="empty tray"),
    )

    assert meta["source"] == "hard_negative"
    assert meta["previous_source"] == "manual_camera_capture"
    assert meta["boxes"] == []
    assert classify_dataset_item(meta).state is DatasetTrustState.HARD_NEGATIVE
    assert is_trainable_meta(meta) is False


def test_holdout_is_reviewed_but_not_trainable(tmp_path):
    image_path = _write_item(tmp_path / "queue", "holdout", _meta(reviewed=True, needs_annotation=False))

    meta = apply_dataset_review_action(
        image_path,
        DatasetReviewRequest(action="holdout", actor="admin", reason="camera eval"),
    )

    assert meta["holdout"] is True
    assert meta["split"] == "test"
    assert meta["split_lock"] is True
    assert classify_dataset_item(meta).state is DatasetTrustState.HOLDOUT
    assert is_trainable_meta(meta) is False
