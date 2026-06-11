"""Thread-safe, retryable schema bootstrap coordination."""

from __future__ import annotations

from collections.abc import Callable
from threading import Condition


class SchemaReadiness:
    """Run one bootstrap per store key without holding a lock during I/O."""

    def __init__(self) -> None:
        self._condition = Condition()
        self._states: dict[str, str] = {}

    def ensure(self, key: str, bootstrap: Callable[[], None]) -> None:
        with self._condition:
            while self._states.get(key) == "running":
                self._condition.wait()
            if self._states.get(key) == "ready":
                return
            self._states[key] = "running"

        try:
            bootstrap()
        except BaseException:
            with self._condition:
                self._states[key] = "idle"
                self._condition.notify_all()
            raise

        with self._condition:
            self._states[key] = "ready"
            self._condition.notify_all()

    def is_ready(self, key: str) -> bool:
        with self._condition:
            return self._states.get(key) == "ready"

    def reset(self, key: str) -> None:
        with self._condition:
            self._states.pop(key, None)
            self._condition.notify_all()
