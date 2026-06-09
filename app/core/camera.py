"""Camera worker: read frames in QThread, emit via signal."""

from __future__ import annotations

import time
from contextlib import suppress

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

from app.core.frame_transform import apply_camera_transform
from app.utils.camera_frame_quality import evaluate_frame_quality
from app.utils.camera_source import backend_hint, normalize_camera_source
from app.utils.logging import logger
from app.utils.shared_camera_stream import read_shared_frame


class CameraWorker(QThread):
    frame_ready = Signal(np.ndarray)
    error = Signal(str)
    connected = Signal(bool)

    def __init__(self, source="", width=1280, height=720, mirror=False, rotation=0):
        super().__init__()
        self._source = source
        self._width = width
        self._height = height
        self._mirror = mirror
        self._rotation = rotation
        self._stop = False
        self._cap: cv2.VideoCapture | None = None

    def _open(self):
        src_raw = normalize_camera_source(self._source)
        is_index = src_raw.isdigit()
        src: int | str = int(src_raw) if is_index else src_raw

        attempts: list[tuple[str, int]] = []
        if is_index:
            # Windows: try DSHOW then MSMF then default. Many UVC/IP cams
            # only respond on one specific backend.
            attempts = [
                ("DSHOW", cv2.CAP_DSHOW),
                ("MSMF", cv2.CAP_MSMF),
                ("ANY", cv2.CAP_ANY),
            ]
            hint = backend_hint(self._source)
            if hint:
                attempts = [item for item in attempts if item[0] == hint]
        else:
            attempts = [("ANY", cv2.CAP_ANY)]

        for name, backend in attempts:
            cap = cv2.VideoCapture(src, backend) if is_index else cv2.VideoCapture(src)
            if not cap.isOpened():
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            with suppress(Exception):
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            quality = _capture_best_quality(cap)
            if not quality.usable:
                logger.warning(
                    "camera source={} backend={} rejected frame: {}",
                    self._source,
                    name,
                    quality.reason,
                )
                cap.release()
                continue
            logger.info("camera open ok source={} backend={}", self._source, name)
            self._cap = cap
            return True
        return False

    def run(self):
        consecutive_fail = 0
        retry_attempts = 0
        while not self._stop:
            if self._cap is None:
                if self._open():
                    self.connected.emit(True)
                    consecutive_fail = 0
                    retry_attempts = 0
                else:
                    retry_attempts += 1
                    self.error.emit(f"open camera failed (attempt {retry_attempts})")
                    self.connected.emit(False)
                    time.sleep(2.0 if retry_attempts >= 3 else 1.0)
                    if retry_attempts >= 3:
                        retry_attempts = 0
                    continue
            cap = self._cap
            if cap is None:
                continue
            ok, frame = cap.read()
            if not ok or frame is None:
                consecutive_fail += 1
                if consecutive_fail >= 5:
                    logger.warning("camera lost, reconnecting")
                    cap.release()
                    self._cap = None
                    self.connected.emit(False)
                continue
            quality = evaluate_frame_quality(frame)
            if not quality.usable:
                consecutive_fail += 1
                if consecutive_fail >= 5:
                    logger.warning("camera black frames, reconnecting: {}", quality.reason)
                    cap.release()
                    self._cap = None
                    self.connected.emit(False)
                continue
            consecutive_fail = 0
            frame = apply_camera_transform(
                frame,
                mirror=self._mirror,
                rotation=self._rotation,
            )
            self.frame_ready.emit(frame)
        if self._cap is not None:
            self._cap.release()

    def stop(self):
        self._stop = True


def _capture_best_quality(cap, *, frames: int = 5):
    qualities = []
    for _ in range(max(1, frames)):
        ok, frame = cap.read()
        if ok and frame is not None:
            qualities.append(evaluate_frame_quality(frame))
        time.sleep(0.03)
    if not qualities:
        return evaluate_frame_quality(None)
    return max(
        qualities,
        key=lambda item: (
            item.usable,
            item.non_black_ratio,
            item.mean_brightness,
            item.variance,
        ),
    )


class SharedCameraWorker(QThread):
    """Read latest frames published by another local runtime."""

    frame_ready = Signal(np.ndarray)
    error = Signal(str)
    connected = Signal(bool)

    def __init__(self, *, poll_interval_s: float = 0.05):
        super().__init__()
        self._poll_interval_s = poll_interval_s
        self._stop = False
        self._connected = False

    def run(self):
        while not self._stop:
            shared = read_shared_frame()
            if shared is None:
                if self._connected:
                    self.connected.emit(False)
                    self._connected = False
                self.error.emit("waiting for shared camera stream")
                time.sleep(0.25)
                continue
            if not self._connected:
                self.connected.emit(True)
                self._connected = True
                logger.info("shared camera stream connected")
            self.frame_ready.emit(shared.frame)
            time.sleep(self._poll_interval_s)
        if self._connected:
            self.connected.emit(False)

    def stop(self):
        self._stop = True
