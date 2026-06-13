import numpy as np

from app.core.events import Detection
from app.core.recognition_test import (
    RecognitionTestRunner,
    RecognitionTestSample,
    RecognitionTestSessionConfig,
)


def _detection(cls_name: str = "Aluminum can", conf: float = 0.91) -> Detection:
    return Detection(
        cls_id=1,
        cls_name=cls_name,
        conf=conf,
        xyxy=(10, 10, 80, 80),
    )


def _runner(*, phase="recognition", repetitions=1, settle=0.0):
    states = []
    trials = []
    armed = []
    runner = RecognitionTestRunner(
        on_state=states.append,
        on_trial_ready=lambda result, _frame, _detections: trials.append(result),
        on_dispatch_arm=armed.append,
    )
    runner.start(
        RecognitionTestSessionConfig(
            samples=(RecognitionTestSample("real can", "Aluminum can"),),
            repetitions=repetitions,
            countdown_seconds=0.0,
            scan_timeout_seconds=1.0,
            stable_frames=3,
            empty_seconds=0.0,
            empty_frames=1,
            busy_settle_seconds=settle,
            phase=phase,
        ),
        session_id="session-1",
        now=0.0,
    )
    return runner, states, trials, armed


def _enter_scanning(runner, frame):
    runner.observe(frame, [], foreground_count=0, now=0.0)
    runner.observe(frame, [], foreground_count=0, now=0.0)
    assert runner.state == "SCANNING"


def test_recognition_trial_requires_three_stable_frames_and_waits_for_empty():
    runner, _states, trials, _armed = _runner(repetitions=2)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    detection = _detection()
    _enter_scanning(runner, frame)

    runner.observe(frame, [detection], foreground_count=1, now=0.1)
    runner.observe(frame, [detection], foreground_count=1, now=0.2)
    assert trials == []
    runner.observe(frame, [detection], foreground_count=1, now=0.3)

    assert len(trials) == 1
    assert trials[0].verdict == "correct"
    assert runner.state == "WAITING_EMPTY"

    for tick in (0.4, 0.5, 0.6):
        runner.observe(frame, [detection], foreground_count=1, now=tick)
    assert len(trials) == 1
    assert runner.state == "WAITING_EMPTY"


def test_recognition_trial_records_multi_object_without_dispatch():
    runner, _states, trials, armed = _runner()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    _enter_scanning(runner, frame)

    for tick in (0.1, 0.2, 0.3):
        runner.observe(
            frame,
            [_detection(), _detection("Plastic bottle")],
            foreground_count=2,
            dispatch_status="multiple waste types (2 visible objects)",
            now=tick,
        )

    assert len(trials) == 1
    assert trials[0].verdict == "multi_object"
    assert trials[0].detection_count == 2
    assert armed == []


def test_recognition_trial_records_no_detection_on_timeout():
    runner, _states, trials, _armed = _runner()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    _enter_scanning(runner, frame)

    runner.observe(frame, [], foreground_count=1, now=1.1)

    assert len(trials) == 1
    assert trials[0].verdict == "no_detection"
    assert trials[0].predicted_class is None


def test_servo_trial_waits_for_ack_before_completing():
    runner, states, trials, armed = _runner(phase="servo")
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    detection = _detection()
    _enter_scanning(runner, frame)

    for tick in (0.1, 0.2, 0.3):
        runner.observe(frame, [detection], foreground_count=1, now=tick)

    assert runner.state == "WAITING_ACK"
    assert len(armed) == 1
    assert trials == []

    runner.dispatch_started(
        {
            "route": "I",
            "payload": "taiche",
            "speaker_mode": "hardware",
        }
    )
    runner.dispatch_completed({"ack_status": "ok", "rtt_ms": 3400}, now=0.4)
    runner.observe(frame, [detection], foreground_count=1, now=0.4)

    assert len(trials) == 1
    assert trials[0].ack_status == "ok"
    assert trials[0].rtt_ms == 3400
    assert any(state["state"] == "BEEP" for state in states)
