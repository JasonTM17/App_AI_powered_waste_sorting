from pathlib import Path

from scripts.queue_history_captures_for_review import build_metadata


def test_history_recovery_metadata_is_never_trainable_before_review():
    meta = build_metadata(
        {
            "history_id": 12,
            "timestamp": "2026-06-17T10:00:00+00:00",
            "old_label": "Aluminum can",
            "old_confidence": 0.8,
            "current_label": "Pen",
            "current_confidence": 0.7,
            "current_bbox": [10, 20, 100, 120],
            "exact_agreement": False,
            "review_required": True,
            "blur_score": 50.0,
        },
        Path("history.jpg"),
    )

    assert meta["origin_source"] == "history_capture_recovery"
    assert meta["training_excluded"] is True
    assert meta["recognition_enabled"] is False
    assert meta["reviewed"] is False
    assert meta["suggested_label"] == ""
    assert meta["review_priority"] == "high"


def test_matching_models_are_only_a_suggestion():
    meta = build_metadata(
        {
            "history_id": 13,
            "old_label": "Pen",
            "old_confidence": 0.8,
            "current_label": "Pen",
            "current_confidence": 0.9,
            "current_bbox": [0, 0, 10, 10],
            "exact_agreement": True,
            "review_required": False,
        },
        Path("history.jpg"),
    )

    assert meta["suggested_label"] == "Pen"
    assert meta["training_excluded"] is True
