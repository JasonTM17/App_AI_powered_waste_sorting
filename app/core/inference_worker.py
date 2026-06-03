"""Background inference worker.

Runs the heavy ``Pipeline.process_frame`` call off the Qt main thread so
the UI stays responsive. Only the most recent frame is kept; older
unprocessed frames are dropped — better one fresh frame per inference
cycle than a queue that grows unbounded.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
from PySide6.QtCore import QMutex, QThread, QWaitCondition, Signal

logger = logging.getLogger(__name__)


class InferenceWorker(QThread):
    """Consume frames, run pipeline, emit detections.

    The signal is emitted from this background thread but Qt routes it
    via a queued connection to slots on the main thread automatically.
    """

    processed = Signal(object, list, float)  # frame, detections, latency_ms

    def __init__(self, pipeline):
        super().__init__()
        self._pipeline = pipeline
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._latest: np.ndarray | None = None
        self._stop = False

    def submit(self, frame: np.ndarray) -> None:
        """Drop the previously queued frame and replace it with this one."""
        self._mutex.lock()
        try:
            self._latest = frame
            self._cond.wakeOne()
        finally:
            self._mutex.unlock()

    def stop(self) -> None:
        self._mutex.lock()
        try:
            self._stop = True
            self._cond.wakeAll()
        finally:
            self._mutex.unlock()

    def set_pipeline(self, pipeline) -> None:
        self._pipeline = pipeline

    def run(self) -> None:
        import time

        while True:
            self._mutex.lock()
            try:
                while not self._stop and self._latest is None:
                    self._cond.wait(self._mutex)
                if self._stop:
                    return
                frame = self._latest
                self._latest = None
            finally:
                self._mutex.unlock()

            if frame is None or self._pipeline is None:
                continue
            if not self._process_frame(frame, time):
                continue

    def _process_frame(self, frame: np.ndarray, time_module) -> bool:
        t0 = time_module.time()
        try:
            detections = self._pipeline.process_frame(
                frame, datetime.now(timezone.utc)
            )
        except Exception:
            logger.exception("inference worker frame processing failed")
            return False
        latency_ms = (time_module.time() - t0) * 1000.0
        self.processed.emit(frame, detections, latency_ms)
        return True


__all__ = ["InferenceWorker"]
