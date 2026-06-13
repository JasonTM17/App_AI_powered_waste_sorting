"""State machine for guided, repeatable real-waste recognition tests."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal
from uuid import uuid4

import numpy as np

from app.core.events import Detection
from app.core.waste_categories import category_for_known_class

RecognitionTestPhase = Literal["recognition", "servo"]
RecognitionTestState = Literal[
    "IDLE",
    "COUNTDOWN",
    "SCANNING",
    "SAVING",
    "WAITING_ACK",
    "BEEP",
    "WAITING_EMPTY",
    "PAUSED",
    "COMPLETED",
    "ABORTED",
]


@dataclass(frozen=True)
class RecognitionTestSample:
    label: str
    expected_class: str


@dataclass(frozen=True)
class RecognitionTestSessionConfig:
    samples: tuple[RecognitionTestSample, ...]
    repetitions: int = 5
    countdown_seconds: float = 3.0
    scan_timeout_seconds: float = 8.0
    stable_frames: int = 3
    empty_seconds: float = 2.0
    empty_frames: int = 10
    busy_settle_seconds: float = 1.0
    phase: RecognitionTestPhase = "recognition"


@dataclass(frozen=True)
class RecognitionTrialResult:
    id: str
    session_id: str
    sample_index: int
    sample_label: str
    expected_class: str
    expected_route: str
    trial_number: int
    phase: RecognitionTestPhase
    started_at: float
    completed_at: float
    verdict: str
    predicted_class: str | None = None
    predicted_route: str | None = None
    confidence: float | None = None
    bbox: tuple[int, int, int, int] | None = None
    detection_count: int = 0
    guard_reason: str | None = None
    speaker_mode: str | None = None
    uart_payload: str | None = None
    ack_status: str | None = None
    rtt_ms: int | None = None
    raw_image_path: str | None = None
    annotated_image_path: str | None = None
    model_hash: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


TrialReadyCallback = Callable[
    [RecognitionTrialResult, np.ndarray, Sequence[Detection]], None
]
StateCallback = Callable[[dict[str, Any]], None]
DispatchCallback = Callable[[RecognitionTrialResult], None]


class RecognitionTestRunner:
    """Drive countdown, stable recognition, ACK wait, beep, and empty-tray gates."""

    def __init__(
        self,
        *,
        on_state: StateCallback,
        on_trial_ready: TrialReadyCallback,
        on_dispatch_arm: DispatchCallback,
    ) -> None:
        self._on_state = on_state
        self._on_trial_ready = on_trial_ready
        self._on_dispatch_arm = on_dispatch_arm
        self._config: RecognitionTestSessionConfig | None = None
        self._session_id: str | None = None
        self._state: RecognitionTestState = "IDLE"
        self._sample_index = 0
        self._trial_number = 1
        self._deadline = 0.0
        self._scan_started_at = 0.0
        self._empty_started_at: float | None = None
        self._empty_frames = 0
        self._stable_class: str | None = None
        self._stable_count = 0
        self._best_detection: Detection | None = None
        self._pending_result: RecognitionTrialResult | None = None
        self._pending_frame: np.ndarray | None = None
        self._pending_detections: tuple[Detection, ...] = ()
        self._resume_state: RecognitionTestState = "WAITING_EMPTY"

    @property
    def active(self) -> bool:
        return self._state not in {"IDLE", "COMPLETED", "ABORTED"}

    @property
    def state(self) -> RecognitionTestState:
        return self._state

    @property
    def phase(self) -> RecognitionTestPhase | None:
        return self._config.phase if self._config else None

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def pending_result(self) -> RecognitionTrialResult | None:
        return self._pending_result

    def start(
        self,
        config: RecognitionTestSessionConfig,
        *,
        session_id: str | None = None,
        now: float | None = None,
    ) -> str:
        if not config.samples:
            raise ValueError("Recognition test requires at least one sample")
        if config.repetitions < 1 or config.stable_frames < 1:
            raise ValueError("Invalid recognition test repetition/stability settings")
        self._config = config
        self._session_id = session_id or uuid4().hex
        self._sample_index = 0
        self._trial_number = 1
        self._pending_result = None
        self._pending_frame = None
        self._pending_detections = ()
        self._reset_empty_gate()
        self._set_state("WAITING_EMPTY", now=now)
        return self._session_id

    def pause(self) -> None:
        if not self.active or self._state == "PAUSED":
            return
        self._resume_state = self._state
        self._set_state("PAUSED")

    def resume(self, *, now: float | None = None) -> None:
        if self._state != "PAUSED":
            return
        target = self._resume_state
        if target in {"COUNTDOWN", "SCANNING"}:
            target = "WAITING_EMPTY"
            self._reset_empty_gate()
        self._set_state(target, now=now)

    def abort(self) -> None:
        if self._state in {"IDLE", "COMPLETED", "ABORTED"}:
            return
        self._set_state("ABORTED")

    def observe(
        self,
        frame: np.ndarray,
        detections: Sequence[Detection],
        *,
        dispatch_status: str = "",
        foreground_count: int = 0,
        now: float | None = None,
    ) -> None:
        if not self.active or self._state == "PAUSED":
            return
        config = self._config
        if config is None:
            return
        current = time.monotonic() if now is None else now
        visible_count = max(foreground_count, len(detections))

        if self._state == "WAITING_ACK":
            if current >= self._deadline and self._pending_result is not None:
                self._pending_result = replace(
                    self._pending_result,
                    completed_at=time.time(),
                    ack_status="timeout",
                    guard_reason=dispatch_status or "ACK timeout",
                )
                self._deadline = current
                self._set_state("BEEP", now=current)
            return

        if self._state == "BEEP":
            if current >= self._deadline:
                self._finish_pending_trial()
            return

        if self._state == "WAITING_EMPTY":
            if visible_count > 0:
                self._reset_empty_gate()
                return
            if self._empty_started_at is None:
                self._empty_started_at = current
            self._empty_frames += 1
            if (
                self._empty_frames >= config.empty_frames
                and current - self._empty_started_at >= config.empty_seconds
            ):
                self._deadline = current + config.countdown_seconds
                self._set_state("COUNTDOWN", now=current)
            return

        if self._state == "COUNTDOWN":
            if current >= self._deadline:
                self._scan_started_at = current
                self._stable_class = None
                self._stable_count = 0
                self._best_detection = None
                self._set_state("SCANNING", now=current)
            else:
                self._emit_state(now=current)
            return

        if self._state != "SCANNING":
            return

        status_lower = dispatch_status.lower()
        is_multi = (
            visible_count > 1
            or "multiple waste types" in status_lower
            or "visible objects" in status_lower
        )
        if is_multi:
            self._stable_class = "__multi__"
            self._stable_count += 1
            if self._stable_count >= config.stable_frames:
                self._complete_scan(
                    frame,
                    detections,
                    verdict="multi_object",
                    guard_reason=dispatch_status or "Multiple visible objects",
                    now=current,
                )
            return

        detection = max(detections, key=lambda item: item.conf, default=None)
        if detection is not None:
            if (
                self._best_detection is None
                or detection.conf > self._best_detection.conf
            ):
                self._best_detection = detection
            if detection.cls_name == self._stable_class:
                self._stable_count += 1
            else:
                self._stable_class = detection.cls_name
                self._stable_count = 1
            if self._stable_count >= config.stable_frames:
                self._complete_scan(frame, detections, now=current)
                return
        else:
            self._stable_class = None
            self._stable_count = 0

        if current - self._scan_started_at >= config.scan_timeout_seconds:
            verdict = "unstable" if self._best_detection is not None else "no_detection"
            self._complete_scan(
                frame,
                detections,
                verdict=verdict,
                guard_reason=dispatch_status or verdict.replace("_", " "),
                now=current,
            )
        else:
            self._emit_state(now=current)

    def dispatch_started(self, evidence: dict[str, Any]) -> None:
        if self._state != "WAITING_ACK" or self._pending_result is None:
            return
        self._pending_result = replace(
            self._pending_result,
            predicted_class=evidence.get(
                "predicted_class", self._pending_result.predicted_class
            ),
            predicted_route=evidence.get(
                "route", self._pending_result.predicted_route
            ),
            confidence=evidence.get("confidence", self._pending_result.confidence),
            speaker_mode=evidence.get("speaker_mode"),
            uart_payload=evidence.get("payload"),
            extra={**self._pending_result.extra, "dispatch": evidence},
        )
        self._emit_state()

    def dispatch_completed(
        self,
        evidence: dict[str, Any],
        *,
        now: float | None = None,
    ) -> None:
        if self._state != "WAITING_ACK" or self._pending_result is None:
            return
        current = time.monotonic() if now is None else now
        self._pending_result = replace(
            self._pending_result,
            completed_at=time.time(),
            ack_status=evidence.get("ack_status"),
            rtt_ms=evidence.get("rtt_ms"),
            extra={**self._pending_result.extra, "ack": evidence},
        )
        assert self._config is not None
        self._deadline = current + self._config.busy_settle_seconds
        self._set_state("BEEP", now=current)

    def state_payload(self, *, now: float | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "state": self._state,
            "session_id": self._session_id,
            "active": self.active,
            "sample_index": self._sample_index,
            "trial_number": self._trial_number,
        }
        if self._config and self._sample_index < len(self._config.samples):
            sample = self._config.samples[self._sample_index]
            payload.update(
                {
                    "sample_label": sample.label,
                    "expected_class": sample.expected_class,
                    "repetitions": self._config.repetitions,
                    "sample_count": len(self._config.samples),
                    "phase": self._config.phase,
                }
            )
        current = time.monotonic() if now is None else now
        if self._state == "COUNTDOWN":
            payload["remaining_seconds"] = max(0.0, self._deadline - current)
        elif self._state == "SCANNING":
            assert self._config is not None
            payload["remaining_seconds"] = max(
                0.0,
                self._config.scan_timeout_seconds - (current - self._scan_started_at),
            )
            payload["stable_frames"] = self._stable_count
        if self._pending_result is not None:
            payload["pending_result"] = self._pending_result.to_dict()
        return payload

    def _complete_scan(
        self,
        frame: np.ndarray,
        detections: Sequence[Detection],
        *,
        verdict: str | None = None,
        guard_reason: str | None = None,
        now: float,
    ) -> None:
        assert self._config is not None and self._session_id is not None
        sample = self._config.samples[self._sample_index]
        detection = max(detections, key=lambda item: item.conf, default=None)
        if detection is None:
            detection = self._best_detection
        predicted_class = detection.cls_name if detection else None
        predicted_category = (
            category_for_known_class(predicted_class) if predicted_class else None
        )
        expected_category = category_for_known_class(sample.expected_class)
        if expected_category is None:
            raise ValueError(f"Unsupported expected class: {sample.expected_class}")
        predicted_route = predicted_category.code if predicted_category else None
        expected_route = expected_category.code
        if verdict is None:
            if predicted_class == sample.expected_class:
                verdict = "correct"
            elif predicted_route == expected_route:
                verdict = "wrong_class"
            else:
                verdict = "wrong_route"
        result = RecognitionTrialResult(
            id=uuid4().hex,
            session_id=self._session_id,
            sample_index=self._sample_index,
            sample_label=sample.label,
            expected_class=sample.expected_class,
            expected_route=expected_route,
            trial_number=self._trial_number,
            phase=self._config.phase,
            started_at=time.time() - max(0.0, now - self._scan_started_at),
            completed_at=time.time(),
            verdict=verdict,
            predicted_class=predicted_class,
            predicted_route=predicted_route,
            confidence=detection.conf if detection else None,
            bbox=detection.xyxy if detection else None,
            detection_count=max(len(detections), 2 if verdict == "multi_object" else 0),
            guard_reason=guard_reason,
        )
        self._pending_result = result
        self._pending_frame = frame.copy()
        self._pending_detections = tuple(detections)
        can_dispatch = (
            self._config.phase == "servo"
            and verdict in {"correct", "wrong_class"}
            and predicted_route == expected_route
            and result.detection_count == 1
        )
        if can_dispatch:
            self._deadline = now + max(8.0, self._config.scan_timeout_seconds)
            self._set_state("WAITING_ACK", now=now)
            self._on_dispatch_arm(result)
            return
        self._finish_pending_trial()

    def _finish_pending_trial(self) -> None:
        if self._pending_result is None or self._pending_frame is None:
            return
        result = self._pending_result
        frame = self._pending_frame
        detections = self._pending_detections
        self._set_state("SAVING")
        self._pending_result = None
        self._pending_frame = None
        self._pending_detections = ()
        self._on_trial_ready(result, frame, detections)
        self._set_state("BEEP")
        self._advance()

    def _advance(self) -> None:
        assert self._config is not None
        if self._trial_number < self._config.repetitions:
            self._trial_number += 1
        else:
            self._trial_number = 1
            self._sample_index += 1
        if self._sample_index >= len(self._config.samples):
            self._set_state("COMPLETED")
            return
        self._reset_empty_gate()
        self._set_state("WAITING_EMPTY")

    def _reset_empty_gate(self) -> None:
        self._empty_started_at = None
        self._empty_frames = 0

    def _set_state(
        self,
        state: RecognitionTestState,
        *,
        now: float | None = None,
    ) -> None:
        self._state = state
        self._emit_state(now=now)

    def _emit_state(self, *, now: float | None = None) -> None:
        self._on_state(self.state_payload(now=now))
