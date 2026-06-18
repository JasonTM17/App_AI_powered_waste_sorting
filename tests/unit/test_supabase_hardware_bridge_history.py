from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

from scripts import supabase_hardware_bridge as bridge


class FakeConnection:
    def __init__(self) -> None:
        self.inserts: list[tuple[object, ...]] = []

    def execute(self, sql: str, params=()):
        if "information_schema.tables" in sql:
            return SimpleNamespace(fetchone=lambda: (True,))
        if "insert into public.history" in sql:
            self.inserts.append(tuple(params))
        return SimpleNamespace(fetchone=lambda: None)


class FakeDemoConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, params=()):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, tuple(params)))
        if "from public.demo_hardware_targets" in normalized:
            return SimpleNamespace(fetchall=lambda: [("nguyen-son", "station-a", "station-a-I", 3)])
        return SimpleNamespace(fetchone=lambda: None, fetchall=lambda: [])


class FakeHistoryService:
    rows: ClassVar[list[object]] = []
    closed: ClassVar[bool] = False

    def __init__(self, _path: Path) -> None:
        type(self).closed = False

    def query(self, **_kwargs):
        return list(type(self).rows)

    def close(self) -> None:
        type(self).closed = True


def test_history_sync_skips_unowned_rows_and_keeps_idempotency_key(monkeypatch, tmp_path, caplog) -> None:
    history_db = tmp_path / "history.db"
    history_db.touch()
    FakeHistoryService.rows = [history_row(10, ""), history_row(11, "nguyen-son")]
    bridge._TABLE_EXISTS_CACHE.clear()
    monkeypatch.setattr(bridge, "HistoryService", FakeHistoryService)
    connection = FakeConnection()

    bridge.sync_history(connection, history_db, 200)

    assert FakeHistoryService.closed is True
    assert len(connection.inserts) == 1
    assert connection.inserts[0][0:3] == (11, "eco-1", "nguyen-son")
    assert "without an owner username" in caplog.text


def test_demo_target_applies_fullness_only_to_latest_selected_bin(monkeypatch) -> None:
    bridge._TABLE_EXISTS_CACHE.clear()
    monkeypatch.setenv(bridge.DEMO_TARGET_ENV, "1")
    connection = FakeDemoConnection()

    bridge.sync_demo_hardware_targets(
        connection,
        {
            2: {"fill_percent": 41, "status": "normal"},
            3: {"fill_percent": 95, "status": "full"},
        },
    )

    target_query = next(sql for sql, _params in connection.calls if "from public.demo_hardware_targets" in sql)
    bin_update = next(params for sql, params in connection.calls if "update public.bins" in sql)
    alert_sql, alert_params = next(
        (sql, params) for sql, params in connection.calls if "insert into public.alerts" in sql
    )
    assert "order by selected_at desc limit 1" in target_query
    assert bin_update == (95.0, "full", "station-a", 3, "station-a-I", "station-a-I")
    assert "'Thùng rác đã đầy'" in alert_sql
    assert alert_params[3] == "Cảm biến demo báo thùng 3 đã đầy 95%."


def test_fullness_status_thresholds() -> None:
    assert bridge.fullness_status(79.9) == "normal"
    assert bridge.fullness_status(80) == "warning"
    assert bridge.fullness_status(95) == "full"


def history_row(row_id: int, owner: str):
    return SimpleNamespace(
        id=row_id,
        device_id="eco-1",
        owner_username=owner,
        ts="2026-06-18T08:00:00+07:00",
        cls_id=1,
        cls_name="Plastic bottle",
        conf=0.91,
        route_label="Tái chế",
        bin_index=3,
        uart_command="I",
        ack_status="ok",
        rtt_ms=15,
        image_path=None,
        annotated_path=None,
    )
