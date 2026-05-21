"""Camera worker: read frames in QThread, emit via signal."""

from __future__ import annotations

import time

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

from app.utils.logging import logger


class CameraWorker(QThread):
    frame_ready = Signal(np.ndarray)
    error = Signal(str)
    connected = Signal(bool)

    def __init__(self, source="0", width=1280, height=720, mirror=False):
        super().__init__()
        self._source = source
        self._width = width
        self._height = height
        self._mirror = mirror
        self._stop = False
        self._cap = None

    def _open(self):
        src = int(self._source) if self._source.isdigit() else self._source
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            cap.release()
            return False
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._cap = cap
        return True

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
            ok, frame = self._cap.read()
            if not ok or frame is None:
                consecutive_fail += 1
                if consecutive_fail >= 5:
                    logger.warning("camera lost, reconnecting")
                    self._cap.release()
                    self._cap = None
                    self.connected.emit(False)
                continue
            consecutive_fail = 0
            if self._mirror:
                frame = cv2.flip(frame, 1)
            self.frame_ready.emit(frame)
        if self._cap is not None:
            self._cap.release()

    def stop(self):
        self._stop = True
