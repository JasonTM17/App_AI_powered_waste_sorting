from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest

from scripts import supabase_bridge_resilience as resilience


class _DatabaseError(psycopg.OperationalError):
    def __init__(self, sqlstate: str):
        self._sqlstate = sqlstate
        super().__init__(f"database error {sqlstate}")

    @property
    def sqlstate(self):
        return self._sqlstate


class _Connection:
    def __init__(self):
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, sql: str, params=()):
        self.executed.append((" ".join(sql.split()), tuple(params)))
        return SimpleNamespace(fetchone=lambda: None)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_transaction_domain_retries_only_transient_sqlstates(monkeypatch) -> None:
    connection = _Connection()
    attempts = 0
    sleeps: list[float] = []
    resets = 0

    def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise _DatabaseError("55P03")
        return "ok"

    def reset():
        nonlocal resets
        resets += 1

    monkeypatch.setattr(resilience.random, "uniform", lambda _low, _high: 1.0)
    monkeypatch.setattr(resilience.time, "sleep", sleeps.append)

    result = resilience.run_transaction_domain(
        connection,
        "history",
        operation,
        lock_timeout_ms=2000,
        statement_timeout_ms=15000,
        reset_caches=reset,
    )

    assert result == "ok"
    assert attempts == 3
    assert connection.rollbacks == 2
    assert connection.commits == 1
    assert resets == 2
    assert sleeps == [0.25, 0.5]
    assert ("select set_config('lock_timeout', %s, true)", ("2000ms",)) in connection.executed
    assert (
        "select set_config('statement_timeout', %s, true)",
        ("15000ms",),
    ) in connection.executed


def test_transaction_domain_does_not_retry_statement_timeout(monkeypatch) -> None:
    connection = _Connection()
    monkeypatch.setattr(resilience.time, "sleep", lambda _delay: pytest.fail("unexpected retry"))

    with pytest.raises(psycopg.OperationalError):
        resilience.run_transaction_domain(
            connection,
            "training",
            lambda: (_ for _ in ()).throw(_DatabaseError("57014")),
            lock_timeout_ms=2000,
            statement_timeout_ms=15000,
        )

    assert connection.rollbacks == 1
    assert connection.commits == 0


def test_bridge_heartbeat_round_trip_and_staleness(tmp_path, monkeypatch) -> None:
    heartbeat = tmp_path / "bridge" / "heartbeat.json"
    monkeypatch.setattr(resilience.time, "time", lambda: 100.0)

    resilience.write_heartbeat(heartbeat)

    assert resilience.heartbeat_is_fresh(heartbeat, 30.0) is True
    monkeypatch.setattr(resilience.time, "time", lambda: 131.0)
    assert resilience.heartbeat_is_fresh(heartbeat, 30.0) is False
    assert resilience.heartbeat_is_fresh(Path("missing-heartbeat.json"), 30.0) is False
