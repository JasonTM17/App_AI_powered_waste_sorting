import json
from pathlib import Path

from scripts.summarize_history_recovery_queue import build_markdown


def test_manifest_states_history_labels_are_not_ground_truth():
    markdown = build_markdown(
        [
            {
                "history_id": 12,
                "review_priority": "high",
                "old_model_label": "Aluminum can",
                "current_model_label": "Pen",
                "current_model_confidence": 0.7,
                "training_excluded": True,
                "recognition_enabled": False,
                "reviewed": False,
                "image_path": "dataset_v2/low_conf_queue/history_recovery_000012.jpg",
                "exact_agreement": False,
                "route_agreement": False,
                "visual_status": "",
                "visual_note": "",
            }
        ],
        queue=Path("dataset_v2/low_conf_queue"),
        audit=Path("runs/eval/history-capture-model-audit.json"),
        limit=10,
    )

    assert "Old history labels are model predictions, not human ground truth." in markdown
    assert "Do not train from any `history_recovery_*.jpg`" in markdown
    assert "| 12 | high | Aluminum can | Pen | 0.70 | no | no |" in markdown


def test_manifest_loader_keeps_manual_visual_notes(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    (queue / "history_recovery_000750.jpg").write_bytes(b"fake")
    (queue / "history_recovery_000750.json").write_text(
        json.dumps(
            {
                "history_id": 750,
                "review_priority": "high",
                "old_model_label": "Unknown object",
                "current_model_label": "Unknown object",
                "current_model_confidence": 0.0,
                "training_excluded": True,
                "recognition_enabled": False,
                "reviewed": False,
            }
        ),
        encoding="utf-8",
    )

    from scripts.summarize_history_recovery_queue import _load_queue_rows

    rows = _load_queue_rows(queue, {})

    assert rows[0]["visual_status"] == "quarantine"
    assert "do not train" in rows[0]["visual_note"]
