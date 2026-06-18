from __future__ import annotations

from datetime import UTC, datetime

from scripts.seed_supabase_demo_data import demo_history_rows


def test_demo_history_is_deterministic_and_covers_every_recent_day() -> None:
    now = datetime(2026, 6, 18, 12, tzinfo=UTC)
    digest = "0123456789abcdef0123456789abcdef"

    first = demo_history_rows("alice", "demo-device", digest, 240, now)
    second = demo_history_rows("alice", "demo-device", digest, 240, now)

    assert first == second
    assert len(first) == 240
    day_offsets = {(now.date() - datetime.fromisoformat(row["ts"]).date()).days for row in first}
    assert set(range(180)).issubset(day_offsets)
    assert len({row["local_history_id"] for row in first}) == 240
    assert {row["uart_command"] for row in first} == {"O", "R", "I"}
