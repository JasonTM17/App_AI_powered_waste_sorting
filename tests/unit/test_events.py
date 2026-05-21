from datetime import UTC, datetime

import numpy as np

from app.core.events import AckEvent, Detection, DetectionEvent, TrackedDetection


def test_detection_immutable():
    d = Detection(cls_id=1, cls_name="plastic", conf=0.92, xyxy=(10, 20, 100, 200))
    assert d.conf == 0.92
    try:
        d.conf = 0.5
        assert False, "should be frozen"
    except Exception:
        pass


def test_tracked_detection_carries_track_id():
    d = Detection(0, "paper", 0.8, (0, 0, 50, 50))
    t = TrackedDetection(track_id=7, detection=d, stable_frames=3, first_seen_ts=1.0)
    assert t.track_id == 7
    assert t.detection.cls_name == "paper"


def test_detection_event_holds_frame():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    e = DetectionEvent(
        track_id=1,
        cls_id=0,
        cls_name="paper",
        conf=0.9,
        frame=frame,
        ts=datetime.now(UTC),
    )
    assert e.frame.shape == (10, 10, 3)


def test_ack_event_status_literal():
    a = AckEvent(track_id=1, command="P", status="ok", rtt_ms=42)
    assert a.status == "ok"
