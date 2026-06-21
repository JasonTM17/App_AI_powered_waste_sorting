from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np

from app.core.auto_review_queue import AutoReviewQueue
from app.core.events import Detection


def test_auto_review_queue_saves_pending_item_with_reason(tmp_path):
    queue = AutoReviewQueue(tmp_path, cooldown_seconds=30, catalog_path=tmp_path / "dataset.db")
    frame = np.full((80, 120, 3), 180, dtype=np.uint8)
    detection = Detection(999, "Unknown object", 0.21, (20, 10, 90, 70))

    image_path = queue.capture(
        frame,
        [detection],
        reason="unknown_object",
        ts=datetime.now(UTC),
    )

    assert image_path is not None
    metadata = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert metadata["needs_annotation"] is True
    assert metadata["training_excluded"] is True
    assert metadata["queue_reason"] == "unknown_object"
    assert metadata["object_signature"]
    assert metadata["session_id"].startswith("auto_review_")
    assert metadata["review_priority"] == "high"
    assert metadata["suggested_label"] == ""
    assert metadata["is_screenshot_audit"] is False
    assert metadata["boxes"][0]["cls_name"] == "Unknown object"


def test_auto_review_queue_deduplicates_near_identical_frames(tmp_path):
    queue = AutoReviewQueue(tmp_path, cooldown_seconds=30, catalog_path=tmp_path / "dataset.db")
    frame = np.full((80, 120, 3), 180, dtype=np.uint8)
    detection = Detection(999, "Unknown object", 0.21, (20, 10, 90, 70))

    first = queue.capture(frame, [detection], reason="unknown_object", ts=datetime.now(UTC))
    second = queue.capture(frame, [detection], reason="unknown_object", ts=datetime.now(UTC))

    assert first is not None
    assert second is None
    assert len(list(tmp_path.glob("*.jpg"))) == 1


def test_auto_review_queue_deduplicates_same_object_even_when_brightness_changes(tmp_path):
    queue = AutoReviewQueue(tmp_path, cooldown_seconds=30, catalog_path=tmp_path / "dataset.db")
    first_frame = np.full((80, 120, 3), 170, dtype=np.uint8)
    second_frame = np.full((80, 120, 3), 205, dtype=np.uint8)
    detection = Detection(42, "Pen", 0.42, (12, 35, 108, 52), operator_label="But bi")

    first = queue.capture(first_frame, [detection], reason="low_confidence", ts=datetime.now(UTC))
    second = queue.capture(second_frame, [detection], reason="low_confidence", ts=datetime.now(UTC))

    assert first is not None
    assert second is None
    assert len(list(tmp_path.glob("*.jpg"))) == 1


def test_auto_review_queue_allows_different_object_signatures(tmp_path):
    queue = AutoReviewQueue(tmp_path, cooldown_seconds=30, catalog_path=tmp_path / "dataset.db")
    frame = np.full((80, 120, 3), 180, dtype=np.uint8)
    pen = Detection(42, "Pen", 0.41, (10, 35, 108, 52), operator_label="But bi")
    battery = Detection(43, "Battery", 0.44, (30, 20, 76, 62), operator_label="Pin AA/AAA")

    first = queue.capture(frame, [pen], reason="low_confidence", ts=datetime.now(UTC))
    second = queue.capture(frame, [battery], reason="hazardous_battery", ts=datetime.now(UTC))

    assert first is not None
    assert second is not None
    metadata = json.loads(second.with_suffix(".json").read_text(encoding="utf-8"))
    assert metadata["review_priority"] == "hazardous"
    assert metadata["suggested_label"] == "Pin AA/AAA"
    assert len(list(tmp_path.glob("*.jpg"))) == 2


def test_auto_review_queue_persists_dedupe_across_restart(tmp_path):
    catalog_path = tmp_path / "dataset.db"
    frame = np.full((80, 120, 3), 180, dtype=np.uint8)
    detection = Detection(999, "Unknown object", 0.20, (20, 10, 90, 70))
    first_queue = AutoReviewQueue(tmp_path, cooldown_seconds=30, catalog_path=catalog_path)

    first = first_queue.capture(
        frame,
        [detection],
        reason="unknown_object",
        ts=datetime.now(UTC),
    )
    restarted_queue = AutoReviewQueue(tmp_path, cooldown_seconds=30, catalog_path=catalog_path)
    second = restarted_queue.capture(
        frame.copy(),
        [detection],
        reason="unknown_object",
        ts=datetime.now(UTC),
    )

    assert first is not None
    assert second is None
    assert len(list(tmp_path.glob("*.jpg"))) == 1
