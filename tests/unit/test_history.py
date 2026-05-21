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
        uart_command="P",
        ack_status="pending",
    )
    assert rid > 0
    rows = svc.query(limit=10)
    assert len(rows) == 1
    assert rows[0].cls_name == "paper"
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
