"""Shared latest-frame handoff for desktop and web camera runtimes."""

from __future__ import annotations

import os
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.utils.paths import app_data_dir

SHARED_CAMERA_STALE_AFTER_S = 2.0


@dataclass(frozen=True)
class SharedFrame:
    frame: np.ndarray
    jpeg: bytes
    age_s: float


class SharedFramePublisher:
    def __init__(self, *, min_interval_s: float = 0.08, max_width: int = 960):
        self.min_interval_s = min_interval_s
        self.max_width = max_width
        self._last_publish = 0.0
        self._path = shared_frame_path()

    def publish(self, frame: np.ndarray) -> None:
        now = time.monotonic()
        if now - self._last_publish < self.min_interval_s:
            return
        self._last_publish = now
        jpeg = encode_shared_frame(frame, max_width=self.max_width)
        if not jpeg:
            return
        tmp = self._path.with_suffix(f".{os.getpid()}.tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(jpeg)
            os.replace(tmp, self._path)
        except OSError:
            with suppress(OSError):
                tmp.unlink()


def shared_frame_path() -> Path:
    return app_data_dir() / "shared-camera" / "latest.jpg"


def encode_shared_frame(frame: np.ndarray, *, max_width: int = 960) -> bytes:
    if max_width and frame.shape[1] > max_width:
        scale = max_width / frame.shape[1]
        height = max(1, int(frame.shape[0] * scale))
        frame = cv2.resize(frame, (max_width, height), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    return buf.tobytes() if ok else b""


def read_shared_frame(*, stale_after_s: float = SHARED_CAMERA_STALE_AFTER_S) -> SharedFrame | None:
    path = shared_frame_path()
    try:
        stat = path.stat()
    except OSError:
        return None
    age_s = time.time() - stat.st_mtime
    if age_s > stale_after_s:
        return None
    try:
        jpeg = path.read_bytes()
    except OSError:
        return None
    arr = np.frombuffer(jpeg, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        return None
    return SharedFrame(frame=frame, jpeg=jpeg, age_s=age_s)


__all__ = [
    "SHARED_CAMERA_STALE_AFTER_S",
    "SharedFrame",
    "SharedFramePublisher",
    "encode_shared_frame",
    "read_shared_frame",
    "shared_frame_path",
]
