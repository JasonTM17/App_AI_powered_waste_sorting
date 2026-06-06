import json
import math

import cv2
import numpy as np

from app.core.capture_session import CaptureSessionManager, evaluate_capture


def _pen_frame(angle: int = 0) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    frame = np.zeros((180, 320, 3), dtype=np.uint8)
    frame[:] = (35, 35, 35)
    radians = math.radians(angle)
    center = (160, 90)
    dx = int(math.cos(radians) * 78)
    dy = int(math.sin(radians) * 78)
    start = (center[0] - dx, center[1] - dy)
    end = (center[0] + dx, center[1] + dy)
    cv2.line(frame, start, end, (20, 30, 230), 12)
    return frame, (
        min(start[0], end[0]) - 12,
        min(start[1], end[1]) - 12,
        max(start[0], end[0]) + 12,
        max(start[1], end[1]) + 12,
    )


def test_capture_quality_rejects_duplicate():
    frame, bbox = _pen_frame()
    first = evaluate_capture(frame, bbox, [])
    assert first["accepted"] is True

    duplicate = evaluate_capture(frame, bbox, [int(first["hash_value"])])
    assert duplicate["accepted"] is False
    assert "similar" in str(duplicate["message"])


def test_capture_session_saves_split_locked_holdout(tmp_path):
    manager = CaptureSessionManager(tmp_path / "queue", tmp_path / "dataset.db")
    manager.start("Pen", 42, target_count=4, holdout_count=1)

    for angle in (0, 25, 60, 90):
        frame, bbox = _pen_frame(angle)
        state = manager.capture(frame, bbox, pose_index=angle)

    assert state["accepted_count"] == 4
    assert state["training_count"] == 3
    assert state["holdout_accepted"] == 1
    assert state["active"] is False
    metas = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (tmp_path / "queue").glob("*.json")
    ]
    assert sum(bool(meta["holdout"]) for meta in metas) == 1
    assert all(meta["split_lock"] is True for meta in metas)
    assert all(meta["reviewed"] is False for meta in metas)
