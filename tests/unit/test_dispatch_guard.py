from app.core.dispatch_guard import DispatchGuard


def _guard() -> DispatchGuard:
    return DispatchGuard(
        min_sort_interval_seconds=12,
        busy_settle_seconds=1,
        min_stable_frames=3,
        empty_rearm_seconds=2,
        empty_rearm_frames=10,
    )


def _arm(guard: DispatchGuard) -> None:
    for index in range(10):
        guard.observe_frame(has_visible_object=False, roi_ready=True, now=float(index) * 0.25)


def test_roi_off_blocks_dispatch_and_disarms():
    guard = _guard()
    _arm(guard)

    guard.observe_frame(has_visible_object=False, roi_ready=False, now=3.0)
    decision = guard.evaluate(
        track_id=1,
        stable_frames=3,
        in_roi=True,
        roi_ready=False,
        now=3.1,
    )

    assert decision.allowed is False
    assert decision.reason == "ROI OFF"


def test_requires_stable_frames_before_dispatch():
    guard = _guard()
    _arm(guard)

    decision = guard.evaluate(
        track_id=1,
        stable_frames=2,
        in_roi=True,
        roi_ready=True,
        now=3.0,
    )

    assert decision.allowed is False
    assert decision.reason == "waiting stable"


def test_first_stable_object_dispatches_after_empty_rearm():
    guard = _guard()
    _arm(guard)

    decision = guard.evaluate(
        track_id=1,
        stable_frames=3,
        in_roi=True,
        roi_ready=True,
        now=3.0,
    )

    assert decision.allowed is True
    assert guard.state == "DETECTING"


def test_busy_blocks_until_ack_timeout_and_settle():
    guard = _guard()
    _arm(guard)
    guard.begin_dispatch(track_id=1, now=3.0, ack_timeout_seconds=4.5)

    blocked = guard.evaluate(
        track_id=2,
        stable_frames=3,
        in_roi=True,
        roi_ready=True,
        now=7.0,
    )
    expired = guard.evaluate(
        track_id=2,
        stable_frames=3,
        in_roi=True,
        roi_ready=True,
        now=8.6,
    )

    assert blocked.allowed is False
    assert blocked.reason == "sort busy"
    assert guard.state == "WAITING_EMPTY"
    assert expired.allowed is False
    assert expired.reason == "waiting empty tray"


def test_guard_reports_ready_sorting_returning_and_waiting_states():
    guard = _guard()
    _arm(guard)
    assert guard.state == "READY"

    guard.begin_dispatch(track_id=1, now=3.0, ack_timeout_seconds=4.5)
    assert guard.state == "SORTING"

    guard.complete_dispatch(track_id=1, now=4.0)
    assert guard.state == "RETURNING"

    guard.observe_frame(has_visible_object=False, roi_ready=True, now=5.1)
    assert guard.state == "WAITING_EMPTY"


def test_cooldown_blocks_back_to_back_sorts_after_rearm():
    guard = _guard()
    _arm(guard)
    guard.begin_dispatch(track_id=1, now=3.0, ack_timeout_seconds=0)
    guard.complete_dispatch(track_id=1, now=3.0)
    for index in range(10):
        guard.observe_frame(has_visible_object=False, roi_ready=True, now=4.1 + index * 0.25)

    decision = guard.evaluate(
        track_id=2,
        stable_frames=3,
        in_roi=True,
        roi_ready=True,
        now=7.0,
    )

    assert decision.allowed is False
    assert decision.reason == "cooldown"


def test_same_visible_object_does_not_rearm_after_dispatch():
    guard = _guard()
    _arm(guard)
    guard.begin_dispatch(track_id=1, now=3.0, ack_timeout_seconds=0)
    guard.complete_dispatch(track_id=1, now=3.0)
    for index in range(20):
        guard.observe_frame(has_visible_object=True, roi_ready=True, now=4.1 + index * 0.25)

    decision = guard.evaluate(
        track_id=2,
        stable_frames=3,
        in_roi=True,
        roi_ready=True,
        now=20.0,
    )

    assert decision.allowed is False
    assert decision.reason == "waiting empty tray"
