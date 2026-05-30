from types import SimpleNamespace

import numpy as np

from app.core.events import Detection, TrackedDetection
from app.core.multi_object_dispatch import (
    evaluate_foreground_multi_object_dispatch,
    evaluate_single_class_dispatch,
)


def _tracked(cls_name: str, track_id: int) -> TrackedDetection:
    return TrackedDetection(
        track_id=track_id,
        detection=Detection(track_id, cls_name, 0.9, (0, 0, 10, 10)),
        stable_frames=1,
        first_seen_ts=0.0,
    )


def _roi(width: int = 320, height: int = 240):
    return SimpleNamespace(enabled=True, x=0, y=0, width=width, height=height)


def _two_object_frame() -> np.ndarray:
    frame = np.full((240, 320, 3), 245, dtype=np.uint8)
    frame[24:164, 24:92] = (35, 35, 35)
    frame[56:200, 160:280] = (210, 85, 35)
    return frame


def test_multi_object_dispatch_allows_one_object():
    decision = evaluate_single_class_dispatch(
        [_tracked("Pen", 1)],
        in_roi=lambda _bbox: True,
        max_objects=1,
        max_classes=1,
    )

    assert decision.allowed is True
    assert decision.class_names == ("Pen",)


def test_multi_object_dispatch_blocks_same_class_pair_in_roi():
    decision = evaluate_single_class_dispatch(
        [_tracked("Pen", 1), _tracked("Pen", 2)],
        in_roi=lambda _bbox: True,
        max_objects=1,
        max_classes=1,
    )

    assert decision.allowed is False
    assert decision.class_names == ("Pen",)
    assert decision.reason == "multiple waste types"


def test_multi_object_dispatch_blocks_multiple_classes_in_roi():
    decision = evaluate_single_class_dispatch(
        [_tracked("Pen", 1), _tracked("Textile", 2)],
        in_roi=lambda _bbox: True,
        max_objects=1,
        max_classes=1,
    )

    assert decision.allowed is False
    assert decision.class_names == ("Pen", "Textile")
    assert decision.reason == "multiple waste types"


def test_foreground_multi_object_dispatch_blocks_two_visible_objects():
    decision = evaluate_foreground_multi_object_dispatch(
        _two_object_frame(),
        roi=_roi(),
        max_objects=1,
        min_area_ratio=0.002,
    )

    assert decision.allowed is False
    assert decision.object_count == 2
    assert decision.reason == "multiple waste types (2 visible objects)"
    assert decision.class_names == ("2 visible objects",)


def test_foreground_multi_object_dispatch_allows_one_visible_object():
    frame = np.full((240, 320, 3), 245, dtype=np.uint8)
    frame[40:180, 80:220] = (30, 30, 30)

    decision = evaluate_foreground_multi_object_dispatch(
        frame,
        roi=_roi(),
        max_objects=1,
        min_area_ratio=0.002,
    )

    assert decision.allowed is True
    assert decision.object_count == 1
