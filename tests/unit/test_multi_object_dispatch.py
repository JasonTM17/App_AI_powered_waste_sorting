from types import SimpleNamespace

import cv2
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


def test_foreground_fragments_without_yolo_reference_count_as_one_object():
    frame = np.full((240, 320, 3), 245, dtype=np.uint8)
    frame[86:132, 80:170] = (35, 35, 35)
    frame[96:124, 180:216] = (70, 70, 70)

    decision = evaluate_foreground_multi_object_dispatch(
        frame,
        roi=_roi(),
        max_objects=1,
        min_area_ratio=0.002,
    )

    assert decision.allowed is True
    assert decision.object_count == 1
    assert decision.foreground_count == 2


def test_crumpled_paper_folds_without_yolo_reference_count_as_one_object():
    frame = np.full((260, 360, 3), 228, dtype=np.uint8)
    paper = np.array(
        [
            [82, 76],
            [268, 50],
            [314, 145],
            [236, 218],
            [94, 199],
            [46, 126],
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(frame, [paper], (218, 220, 222))
    cv2.line(frame, (72, 123), (286, 87), (56, 56, 58), 18)
    cv2.line(frame, (94, 176), (250, 188), (74, 74, 76), 14)
    cv2.line(frame, (112, 88), (210, 210), (190, 190, 192), 7)

    decision = evaluate_foreground_multi_object_dispatch(
        frame,
        roi=_roi(width=360, height=260),
        max_objects=1,
        min_area_ratio=0.002,
    )

    assert decision.allowed is True
    assert decision.object_count == 1
    assert decision.foreground_count >= 2


def test_close_foreground_objects_without_yolo_reference_stay_blocked():
    frame = np.full((240, 320, 3), 245, dtype=np.uint8)
    frame[70:130, 60:130] = (35, 35, 35)
    frame[75:135, 144:214] = (70, 70, 70)

    decision = evaluate_foreground_multi_object_dispatch(
        frame,
        roi=_roi(),
        max_objects=1,
        min_area_ratio=0.002,
    )

    assert decision.allowed is False
    assert decision.object_count == 2
    assert decision.foreground_count == 2


def test_foreground_components_inside_one_yolo_box_count_as_one_object():
    decision = evaluate_foreground_multi_object_dispatch(
        _two_object_frame(),
        roi=_roi(),
        max_objects=1,
        min_area_ratio=0.002,
        reference_boxes=((20, 20, 285, 205),),
    )

    assert decision.allowed is True
    assert decision.object_count == 1
    assert decision.foreground_count == 2
    assert decision.reference_count == 1
    assert decision.unmatched_foreground_count == 0


def test_foreground_component_outside_yolo_box_still_counts_as_second_object():
    decision = evaluate_foreground_multi_object_dispatch(
        _two_object_frame(),
        roi=_roi(),
        max_objects=1,
        min_area_ratio=0.002,
        reference_boxes=((20, 20, 100, 170),),
    )

    assert decision.allowed is False
    assert decision.object_count == 2
    assert decision.unmatched_foreground_count == 1


def test_nearby_glossy_fragment_is_grouped_with_reference_object():
    frame = np.full((240, 320, 3), 245, dtype=np.uint8)
    frame[50:190, 70:180] = (35, 35, 35)
    frame[80:150, 195:205] = (210, 85, 35)

    decision = evaluate_foreground_multi_object_dispatch(
        frame,
        roi=_roi(),
        max_objects=1,
        min_area_ratio=0.002,
        reference_boxes=((65, 45, 190, 195),),
    )

    assert decision.allowed is True
    assert decision.object_count == 1
    assert decision.foreground_count == 2
    assert decision.unmatched_foreground_count == 0


def test_adjacent_thin_shadow_is_grouped_with_long_reference_object():
    frame = np.full((240, 320, 3), 245, dtype=np.uint8)
    frame[96:126, 42:238] = (35, 35, 35)
    frame[140:158, 54:220] = (85, 85, 85)

    decision = evaluate_foreground_multi_object_dispatch(
        frame,
        roi=_roi(),
        max_objects=1,
        min_area_ratio=0.002,
        reference_boxes=((38, 90, 242, 130),),
    )

    assert decision.allowed is True
    assert decision.object_count == 1
    assert decision.foreground_count == 2
    assert decision.unmatched_foreground_count == 0


def test_two_yolo_boxes_stay_blocked_even_when_foreground_merges_cleanly():
    decision = evaluate_foreground_multi_object_dispatch(
        _two_object_frame(),
        roi=_roi(),
        max_objects=1,
        min_area_ratio=0.002,
        reference_boxes=((20, 20, 100, 170), (150, 50, 285, 205)),
    )

    assert decision.allowed is False
    assert decision.object_count == 2
    assert decision.reference_count == 2
