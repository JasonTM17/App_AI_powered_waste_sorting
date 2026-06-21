from __future__ import annotations

import json
from datetime import UTC, datetime

from scripts.audit_recognition_failures import build_audit, write_report


def test_audit_marks_clipboard_screenshots_as_not_trainable(tmp_path):
    clipboard_dir = tmp_path / "temp"
    queue_dir = tmp_path / "queue"
    captures_dir = tmp_path / "captures"
    clipboard_dir.mkdir()
    queue_dir.mkdir()
    captures_dir.mkdir()
    screenshot = clipboard_dir / "codex-clipboard-c21cfe9d-9939-4dff-a2d2-5bb53cddb27d.png"
    screenshot.write_bytes(b"not-real-png")

    items, summary = build_audit(
        clipboard_dir=clipboard_dir,
        queue_dir=queue_dir,
        captures_dir=captures_dir,
    )

    assert summary["screenshots"] == 1
    assert items[0].kind == "screenshot_audit"
    assert items[0].true_object == "charger"
    assert items[0].trainable is False

    report = tmp_path / "audit.md"
    write_report(report, items, summary)
    report_text = report.read_text(encoding="utf-8")
    assert "Cục sạc" in report_text
    assert "cá»¥c sáº¡c" not in report_text


def test_audit_ignores_non_recognition_clipboard_screenshots(tmp_path):
    clipboard_dir = tmp_path / "temp"
    queue_dir = tmp_path / "queue"
    captures_dir = tmp_path / "captures"
    clipboard_dir.mkdir()
    queue_dir.mkdir()
    captures_dir.mkdir()
    (clipboard_dir / "codex-clipboard-demo.png").write_bytes(b"not-real-png")

    items, summary = build_audit(
        clipboard_dir=clipboard_dir,
        queue_dir=queue_dir,
        captures_dir=captures_dir,
    )

    assert summary["screenshots"] == 0
    assert items == []


def test_audit_groups_battery_queue_as_hazardous(tmp_path):
    clipboard_dir = tmp_path / "temp"
    queue_dir = tmp_path / "queue"
    captures_dir = tmp_path / "captures"
    clipboard_dir.mkdir()
    queue_dir.mkdir()
    captures_dir.mkdir()
    image = queue_dir / "auto_review_battery.jpg"
    image.write_bytes(b"jpg")
    image.with_suffix(".json").write_text(
        json.dumps(
            {
                "ts": datetime.now(UTC).isoformat(),
                "source": "auto_review_queue",
                "queue_reason": "hazardous_battery",
                "review_priority": "hazardous",
                "training_excluded": True,
                "boxes": [
                    {
                        "cls_name": "Battery",
                        "operator_label": "Pin AA/AAA",
                        "conf": 0.45,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    items, summary = build_audit(
        clipboard_dir=clipboard_dir,
        queue_dir=queue_dir,
        captures_dir=captures_dir,
    )

    assert summary["target_groups"]["battery"] == 1
    assert summary["queue_priorities"]["hazardous"] == 1
    assert items[0].true_object == "battery"
    assert "Admin" in items[0].action
    assert items[0].trainable is False
