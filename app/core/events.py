"""Immutable event/data classes shared across core modules."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import numpy as np


@dataclass(frozen=True)
class Detection:
    cls_id: int
    cls_name: str
    conf: float
    xyxy: tuple[int, int, int, int]


@dataclass(frozen=True)
class TrackedDetection:
    track_id: int
    detection: Detection
    stable_frames: int
    first_seen_ts: float


@dataclass(frozen=True)
class DetectionEvent:
    track_id: int
    cls_id: int
    cls_name: str
    conf: float
    frame: np.ndarray
    ts: datetime


@dataclass(frozen=True)
class AckEvent:
    track_id: int
    command: str
    status: Literal["ok", "no_ack", "error"]
    rtt_ms: int | None
