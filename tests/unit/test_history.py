from datetime import UTC, datetime
from pathlib import Path

from app.core.history import HistoryService


def test_insert_and_query(tmp_path: Path):
    db = tmp_path / "h.db"
    svc = HistoryService(db)
    rid = svc.insert(
        track_id=1,
        ts=datetime.now(UTC),
        cls_id=0,
        cls_name="paper",
        conf=0.9,
        bbox=(10, 10, 100, 100),
        thumbnail=b"\x00",
        image_path=str(tmp_path / "raw.jpg"),
        annotated_path=str(tmp_path / "annotated.jpg"),
        meta_path=str(tmp_path / "meta.json"),
        route_label="Vô cơ",
        bin_index=2,
        uart_command="P",
        ack_status="pending",
    )
    assert rid > 0
    rows = svc.query(limit=10)
    assert len(rows) == 1
    assert rows[0].cls_name == "paper"
    assert rows[0].annotated_path.endswith("annotated.jpg")
    assert rows[0].route_label == "Tái chế"
    assert rows[0].bin_index == 3
    assert rows[0].uart_command == "I"
    assert svc.get(rid).id == rid
    svc.close()


def test_update_ack(tmp_path: Path):
    db = tmp_path / "h.db"
    svc = HistoryService(db)
    rid = svc.insert(
        track_id=1,
        ts=datetime.now(UTC),
        cls_id=0,
        cls_name="paper",
        conf=0.9,
        bbox=(0, 0, 1, 1),
        thumbnail=b"",
        uart_command="P",
        ack_status="pending",
    )
    svc.update_ack(rid, status="ok", rtt_ms=42)
    row = svc.query(limit=1)[0]
    assert row.ack_status == "ok"
    assert row.rtt_ms == 42
    svc.close()


def test_query_infers_three_bin_route_for_old_rows(tmp_path: Path):
    db = tmp_path / "h.db"
    svc = HistoryService(db)
    svc.insert(
        track_id=1,
        ts=datetime.now(UTC),
        cls_id=0,
        cls_name="Plastic cup",
        conf=0.9,
        bbox=(0, 0, 1, 1),
        thumbnail=b"",
        uart_command="S",
        ack_status="pending",
    )
    row = svc.query(limit=1)[0]
    assert row.route_label == "Tái chế"
    assert row.bin_index == 3
    assert row.uart_command == "I"
    svc.close()


def test_query_normalizes_legacy_command_from_stored_bin(tmp_path: Path):
    db = tmp_path / "h.db"
    svc = HistoryService(db)
    svc.insert(
        track_id=1,
        ts=datetime.now(UTC),
        cls_id=0,
        cls_name="Organic",
        conf=0.9,
        bbox=(0, 0, 1, 1),
        thumbnail=b"",
        route_label="legacy label",
        bin_index=1,
        uart_command="M",
        ack_status="pending",
    )
    row = svc.query(limit=1)[0]
    assert row.route_label == "Hữu cơ"
    assert row.bin_index == 1
    assert row.uart_command == "O"
    svc.close()


def test_export_csv(tmp_path: Path):
    db = tmp_path / "h.db"
    svc = HistoryService(db)
    svc.insert(
        track_id=1,
        ts=datetime.now(UTC),
        cls_id=0,
        cls_name="paper",
        conf=0.9,
        bbox=(0, 0, 1, 1),
        thumbnail=b"",
        uart_command="P",
        ack_status="ok",
        rtt_ms=10,
    )
    out = tmp_path / "h.csv"
    n = svc.export_csv(out)
    assert n == 1
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "paper" in text
    assert "route_label" in text
    svc.close()


def test_stats_by_class(tmp_path: Path):
    db = tmp_path / "h.db"
    svc = HistoryService(db)
    for cls in ("paper", "paper", "plastic"):
        svc.insert(
            track_id=1,
            ts=datetime.now(UTC),
            cls_id=0,
            cls_name=cls,
            conf=0.9,
            bbox=(0, 0, 1, 1),
            thumbnail=b"",
            uart_command="X",
            ack_status="ok",
        )
    counts = svc.count_by_class()
    assert counts.get("paper") == 2
    assert counts.get("plastic") == 1
    svc.close()


def test_query_and_counts_respect_until_and_ack_filters(tmp_path: Path):
    db = tmp_path / "h.db"
    svc = HistoryService(db)
    svc.insert(
        track_id=1,
        ts=datetime(2026, 6, 5, 8, 0, tzinfo=UTC),
        cls_id=0,
        cls_name="Aluminum can",
        conf=0.9,
        bbox=(0, 0, 1, 1),
        thumbnail=b"",
        uart_command="I",
        ack_status="ok",
    )
    svc.insert(
        track_id=2,
        ts=datetime(2026, 6, 10, 8, 0, tzinfo=UTC),
        cls_id=0,
        cls_name="Paper",
        conf=0.9,
        bbox=(0, 0, 1, 1),
        thumbnail=b"",
        uart_command="I",
        ack_status="pending",
    )

    rows = svc.query(
        limit=10,
        since=datetime(2026, 6, 10, 0, 0, tzinfo=UTC),
        until=datetime(2026, 6, 10, 23, 59, 59, tzinfo=UTC),
        ack_status="ok",
    )
    counts = svc.count_by_class(
        since=datetime(2026, 6, 10, 0, 0, tzinfo=UTC),
        until=datetime(2026, 6, 10, 23, 59, 59, tzinfo=UTC),
        ack_status="ok",
    )

    assert rows == []
    assert counts == {}
    svc.close()


def test_count_by_hour(tmp_path):
    from datetime import UTC, datetime

    from app.core.history import HistoryService

    db = tmp_path / "h.db"
    svc = HistoryService(db)
    today = datetime.now(UTC).replace(hour=10, minute=30)
    svc.insert(
        track_id=1,
        ts=today,
        cls_id=0,
        cls_name="paper",
        conf=0.9,
        bbox=(0, 0, 1, 1),
        thumbnail=b"",
        uart_command="P",
        ack_status="ok",
    )
    svc.insert(
        track_id=2,
        ts=today.replace(hour=14),
        cls_id=0,
        cls_name="paper",
        conf=0.9,
        bbox=(0, 0, 1, 1),
        thumbnail=b"",
        uart_command="P",
        ack_status="ok",
    )
    counts = svc.count_by_hour(today)
    assert counts[10] == 1
    assert counts[14] == 1
    svc.close()


def test_qa_sessions_and_trials_are_separate_from_operational_stats(tmp_path):
    svc = HistoryService(tmp_path / "h.db")
    svc.create_qa_session(
        {
            "id": "qa-1",
            "started_at": "2026-06-13T10:00:00",
            "phase": "recognition",
            "status": "running",
            "repetitions": 5,
            "countdown_seconds": 3,
            "scan_timeout_seconds": 8,
            "model_path": "model.pt",
            "model_hash": "abc",
            "sample_count": 1,
            "config": {"samples": ["Aluminum can"]},
        }
    )
    svc.insert_qa_trial(
        {
            "id": "trial-1",
            "session_id": "qa-1",
            "sample_index": 0,
            "sample_label": "real can",
            "expected_class": "Aluminum can",
            "expected_route": "I",
            "trial_number": 1,
            "phase": "recognition",
            "started_at": "2026-06-13T10:00:03",
            "completed_at": "2026-06-13T10:00:04",
            "verdict": "correct",
            "predicted_class": "Aluminum can",
            "predicted_route": "I",
            "confidence": 0.94,
            "bbox": (1, 2, 30, 40),
            "detection_count": 1,
            "raw_image_path": "raw.jpg",
            "annotated_image_path": "annotated.jpg",
            "model_hash": "abc",
        }
    )

    assert svc.query(limit=10) == []
    assert svc.count_by_class() == {}
    assert svc.list_qa_sessions()[0].id == "qa-1"
    trial = svc.query_qa_trials(session_id="qa-1")[0]
    assert trial.expected_class == "Aluminum can"
    assert trial.bbox_x1 == 1
    svc.mark_qa_trial_promoted("trial-1", "queued.jpg")
    assert svc.get_qa_trial("trial-1").promoted_path == "queued.jpg"
    svc.close()
