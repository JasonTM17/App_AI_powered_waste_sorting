from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.inference_worker import InferenceWorker


class _NoOpMutex:
    def lock(self) -> None:
        return None

    def unlock(self) -> None:
        return None


@dataclass
class _DriveCondition:
    worker: InferenceWorker
    calls: int = 0

    def wait(self, _mutex) -> None:
        self.calls += 1
        if self.calls == 1:
            self.worker._latest = np.zeros((2, 2, 3), dtype=np.uint8)
        else:
            self.worker._stop = True

    def wakeOne(self) -> None:  # noqa: N802 - mirrors Qt condition API.
        return None

    def wakeAll(self) -> None:  # noqa: N802 - mirrors Qt condition API.
        return None


class _FlakyPipeline:
    def __init__(self, worker: InferenceWorker):
        self.worker = worker
        self.calls = 0

    def process_frame(self, frame, _ts):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("pipeline failed")
        self.worker._stop = True
        return []


def test_inference_worker_logs_and_keeps_running_after_frame_failure(caplog):
    worker = InferenceWorker(pipeline=None)
    worker._mutex = _NoOpMutex()
    worker._latest = np.zeros((2, 2, 3), dtype=np.uint8)
    worker._stop = False

    pipeline = _FlakyPipeline(worker)
    worker._pipeline = pipeline
    worker._cond = _DriveCondition(worker)

    with caplog.at_level("ERROR"):
        worker.run()

    assert pipeline.calls == 2
    assert "inference worker frame processing failed" in caplog.text
