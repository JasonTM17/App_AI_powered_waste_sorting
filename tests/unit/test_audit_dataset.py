import json
import sys

from PIL import Image

from app.core.waste_categories import TRAINING_CLASS_ORDER_45
from scripts import audit_dataset
from scripts.audit_dataset import (
    _build_blocked_reason_report,
    _build_hard_negative_report,
    _read_yolo_data_yaml,
    _training_class_alignment,
)


def _write_training_order_yaml(path):
    lines = ["nc: 45", "names:"]
    lines.extend(f"  {idx}: {name}" for idx, name in enumerate(TRAINING_CLASS_ORDER_45))
    path.write_text("\n".join(lines), encoding="utf-8")


def test_read_yolo_data_yaml_mapping_names(tmp_path):
    data_yaml = tmp_path / "data.yaml"
    data_yaml.write_text(
        "\n".join(
            [
                "path: dataset",
                "train: images/train",
                "val: images/valid",
                "nc: 2",
                "names:",
                "  0: Paper",
                "  1: Plastic bottle",
            ]
        ),
        encoding="utf-8",
    )

    summary = _read_yolo_data_yaml(data_yaml)

    assert summary["exists"] is True
    assert summary["nc"] == 2
    assert summary["class_total"] == 2
    assert summary["names"] == {0: "Paper", 1: "Plastic bottle"}
    assert summary["errors"] == []


def test_training_class_alignment_blocks_catalog_drift(tmp_path):
    data_yaml = tmp_path / "data.yaml"
    _write_training_order_yaml(data_yaml)
    summary = _read_yolo_data_yaml(data_yaml)

    alignment = _training_class_alignment({"Paper": 10, "Mystery class": 3}, summary)

    assert alignment["matches_training_order"] is True
    assert alignment["promotable_class_contract"] is False
    assert alignment["catalog_classes_not_in_training_order"] == ["Mystery class"]
    assert alignment["catalog_classes_not_in_trainset"] == ["Mystery class"]


def _write_item(queue, stem, meta=None):
    queue.mkdir(parents=True, exist_ok=True)
    image_path = queue / f"{stem}.jpg"
    Image.new("RGB", (100, 80), (220, 220, 220)).save(image_path)
    if meta is not None:
        image_path.with_suffix(".json").write_text(
            json.dumps(meta, ensure_ascii=False),
            encoding="utf-8",
        )
    return image_path


def test_blocked_reason_report_counts_quality_gates(tmp_path):
    queue = tmp_path / "queue"
    _write_item(queue, "missing_meta")
    bad_json = _write_item(queue, "invalid_json", {"source": "manual_import", "boxes": []})
    bad_json.with_suffix(".json").write_text("{ bad json", encoding="utf-8")
    _write_item(queue, "untrusted", {"source": "untrusted", "boxes": []})
    _write_item(
        queue,
        "review_required",
        {
            "source": "auto_low_conf",
            "reviewed": False,
            "boxes": [{"cls_id": 18, "cls_name": "Paper", "xyxy": [1, 1, 20, 20]}],
        },
    )
    _write_item(
        queue,
        "off_taxonomy",
        {
            "source": "manual_import",
            "boxes": [{"cls_id": 99, "cls_name": "Mystery class", "xyxy": [1, 1, 20, 20]}],
        },
    )
    _write_item(
        queue,
        "invalid_bbox",
        {
            "source": "manual_import",
            "boxes": [{"cls_id": 18, "cls_name": "Paper", "xyxy": [20, 20, 1, 1]}],
        },
    )
    _write_item(
        queue,
        "source_issue",
        {
            "source": "manual_web_import",
            "reviewed": True,
            "bbox_reviewed": True,
            "boxes": [{"cls_id": 18, "cls_name": "Paper", "xyxy": [1, 1, 20, 20]}],
        },
    )
    _write_item(
        queue,
        "hard_negative",
        {"source": "hard_negative", "hard_negative": True, "boxes": []},
    )
    _write_item(
        queue,
        "holdout",
        {
            "source": "manual_import",
            "holdout": True,
            "boxes": [{"cls_id": 18, "cls_name": "Paper", "xyxy": [1, 1, 20, 20]}],
        },
    )
    _write_item(
        queue,
        "trainable",
        {
            "source": "manual_import",
            "boxes": [{"cls_id": 18, "cls_name": "Paper", "xyxy": [1, 1, 20, 20]}],
        },
    )

    report = _build_blocked_reason_report(queue)

    assert report["blocked_reasons"]["missing_meta"] == 1
    assert report["blocked_reasons"]["invalid_json"] == 1
    assert report["blocked_reasons"]["untrusted_source"] == 1
    assert report["blocked_reasons"]["review_required"] == 1
    assert report["blocked_reasons"]["off_taxonomy"] == 1
    assert report["blocked_reasons"]["invalid_bbox"] == 1
    assert report["blocked_reasons"]["source_license_issue"] == 1
    assert report["blocked_reasons"]["hard_negative"] == 1
    assert report["quality_reasons"]["holdout_only"] == 1
    assert report["items_with_blocking_reasons"] == 8
    assert report["trainable_by_current_rules"] >= 1


def test_hard_negative_report_counts_reason_and_latest_ts(tmp_path):
    queue = tmp_path / "queue"
    _write_item(
        queue,
        "hand",
        {
            "ts": "2026-06-10T08:00:00",
            "source": "hard_negative",
            "hard_negative": True,
            "hard_negative_reason": "hand_only",
            "expected_outcome": "no_dispatch",
            "boxes": [],
        },
    )
    _write_item(
        queue,
        "cloth",
        {
            "ts": "2026-06-10T09:00:00",
            "source": "hard_negative",
            "hard_negative": True,
            "hard_negative_reason": "cloth_non_waste",
            "expected_outcome": "no_dispatch",
            "boxes": [],
        },
    )

    report = _build_hard_negative_report(queue)

    assert report["total"] == 2
    assert report["by_reason"] == {"cloth_non_waste": 1, "hand_only": 1}
    assert report["by_expected_outcome"] == {"no_dispatch": 2}
    assert report["latest_ts"] == "2026-06-10T09:00:00"


def test_audit_main_writes_quality_json(tmp_path, monkeypatch, capsys):
    queue = tmp_path / "queue"
    _write_item(
        queue,
        "raw_auto",
        {
            "source": "auto_low_conf",
            "reviewed": False,
            "boxes": [{"cls_id": 18, "cls_name": "Paper", "xyxy": [1, 1, 20, 20]}],
        },
    )
    data_yaml = tmp_path / "data.yaml"
    _write_training_order_yaml(data_yaml)
    report_path = tmp_path / "quality.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_dataset.py",
            "--queue",
            str(queue),
            "--db",
            str(tmp_path / "dataset.db"),
            "--trainset-data",
            str(data_yaml),
            "--blocked-reasons",
            "--quality-json",
            str(report_path),
        ],
    )

    assert audit_dataset.main() == 0

    out = capsys.readouterr().out
    assert "Blocked reasons:" in out
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["blocked_reason_report"]["blocked_reasons"]["review_required"] == 1
    assert payload["class_quality"]["Paper"]["blocked_boxes"] == 1
    assert payload["source_gate_table"]["auto_low_conf"]["review_required_images"] == 1
    assert payload["source_quality"]["total_images"] == 1
