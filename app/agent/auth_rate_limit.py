"""Small in-memory login rate limiter for the local agent."""

from __future__ import annotations

from collections import defaultdict
from time import monotonic


class LoginRateLimiter:
    def __init__(self, *, limit: int = 5, window_seconds: float = 60.0):
        self.limit = limit
        self.window_seconds = window_seconds
        self._failures: dict[str, list[float]] = defaultdict(list)

    def is_limited(self, key: str) -> bool:
        now = monotonic()
        failures = self._recent_failures(key, now)
        return len(failures) >= self.limit

    def record_failure(self, key: str) -> None:
        now = monotonic()
        failures = self._recent_failures(key, now)
        failures.append(now)
        self._failures[key] = failures

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)

    def _recent_failures(self, key: str, now: float) -> list[float]:
        cutoff = now - self.window_seconds
        failures = [value for value in self._failures.get(key, []) if value >= cutoff]
        self._failures[key] = failures
        return failures


__all__ = ["LoginRateLimiter"]
