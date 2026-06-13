"""Safety gate for camera-driven hardware dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AutoSortState = Literal[
    "READY",
    "DETECTING",
    "SORTING",
    "RETURNING",
    "WAITING_EMPTY",
]


@dataclass(frozen=True)
class DispatchGuardDecision:
    allowed: bool
    reason: str = ""


class DispatchGuard:
    def __init__(
        self,
        *,
        min_sort_interval_seconds: float = 12.0,
        busy_settle_seconds: float = 1.0,
        min_stable_frames: int = 3,
        empty_rearm_seconds: float = 2.0,
        empty_rearm_frames: int = 10,
    ) -> None:
        self.configure(
            min_sort_interval_seconds=min_sort_interval_seconds,
            busy_settle_seconds=busy_settle_seconds,
            min_stable_frames=min_stable_frames,
            empty_rearm_seconds=empty_rearm_seconds,
            empty_rearm_frames=empty_rearm_frames,
        )
        self.reset()

    def configure(
        self,
        *,
        min_sort_interval_seconds: float,
        busy_settle_seconds: float,
        min_stable_frames: int,
        empty_rearm_seconds: float,
        empty_rearm_frames: int,
    ) -> None:
        self.min_sort_interval_seconds = max(0.0, float(min_sort_interval_seconds))
        self.busy_settle_seconds = max(0.0, float(busy_settle_seconds))
        self.min_stable_frames = max(1, int(min_stable_frames))
        self.empty_rearm_seconds = max(0.0, float(empty_rearm_seconds))
        self.empty_rearm_frames = max(1, int(empty_rearm_frames))

    def reset(self) -> None:
        self._armed = False
        self._empty_since: float | None = None
        self._empty_frames = 0
        self._last_dispatch_started_at: float | None = None
        self._busy_track_id: int | None = None
        self._busy_until = 0.0
        self.state: AutoSortState = "WAITING_EMPTY"
        self.last_reason = "waiting empty tray"

    def observe_frame(self, *, has_visible_object: bool, roi_ready: bool, now: float) -> None:
        self._expire_busy(now)
        if not roi_ready:
            self._armed = False
            self._empty_since = None
            self._empty_frames = 0
            self.state = "WAITING_EMPTY"
            self.last_reason = "ROI OFF"
            return
        if self._is_busy(now):
            self.state = "SORTING" if self._busy_track_id is not None else "RETURNING"
            self.last_reason = "sort busy"
            return
        if has_visible_object:
            self._empty_since = None
            self._empty_frames = 0
            self.state = "DETECTING" if self._armed else "WAITING_EMPTY"
            return
        if self._empty_since is None:
            self._empty_since = now
            self._empty_frames = 1
        else:
            self._empty_frames += 1
        empty_for = now - self._empty_since
        if empty_for >= self.empty_rearm_seconds and self._empty_frames >= self.empty_rearm_frames:
            self._armed = True
            self.state = "READY"
            self.last_reason = ""
        else:
            self.state = "WAITING_EMPTY"
            self.last_reason = "waiting empty tray"

    def evaluate(
        self,
        *,
        track_id: int,
        stable_frames: int,
        in_roi: bool,
        roi_ready: bool,
        now: float,
    ) -> DispatchGuardDecision:
        self._expire_busy(now)
        if not roi_ready:
            return self._block("ROI OFF")
        if not in_roi:
            return self._block("outside ROI")
        if self._is_busy(now):
            return self._block("sort busy")
        if stable_frames < self.min_stable_frames:
            return self._block("waiting stable")
        if not self._armed:
            return self._block("waiting empty tray")
        if self._last_dispatch_started_at is not None:
            elapsed = now - self._last_dispatch_started_at
            if elapsed < self.min_sort_interval_seconds:
                return self._block("cooldown")
        self.state = "DETECTING"
        return DispatchGuardDecision(True)

    def begin_dispatch(self, *, track_id: int, now: float, ack_timeout_seconds: float) -> None:
        self._armed = False
        self._empty_since = None
        self._empty_frames = 0
        self._last_dispatch_started_at = now
        self._busy_track_id = int(track_id)
        timeout = max(0.0, float(ack_timeout_seconds))
        self._busy_until = now + timeout + self.busy_settle_seconds
        self.state = "SORTING"
        self.last_reason = "sort busy"

    def complete_dispatch(self, *, track_id: int, now: float) -> None:
        if self._busy_track_id is not None and self._busy_track_id != int(track_id):
            return
        self._busy_track_id = None
        self._busy_until = now + self.busy_settle_seconds
        self.state = "RETURNING" if self.busy_settle_seconds > 0 else "WAITING_EMPTY"
        self.last_reason = "sort busy" if self.busy_settle_seconds > 0 else "waiting empty tray"

    def _block(self, reason: str) -> DispatchGuardDecision:
        if reason == "sort busy":
            self.state = "SORTING" if self._busy_track_id is not None else "RETURNING"
        elif reason in {"waiting stable", "outside ROI"}:
            self.state = "DETECTING"
        else:
            self.state = "WAITING_EMPTY"
        self.last_reason = reason
        return DispatchGuardDecision(False, reason)

    def _is_busy(self, now: float) -> bool:
        return self._busy_track_id is not None or now < self._busy_until

    def _expire_busy(self, now: float) -> None:
        if self._busy_track_id is not None and now >= self._busy_until:
            self._busy_track_id = None
            self.state = "WAITING_EMPTY"
