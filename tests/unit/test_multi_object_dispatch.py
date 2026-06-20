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


def _spoon_and_pen_frame() -> np.ndarray:
    frame = np.full((480, 640, 3), 235, dtype=np.uint8)
    cv2.line(frame, (0, 180), (300, 162), (76, 76, 78), 62)
    cv2.ellipse(frame, (405, 155), (105, 82), -5, 0, 360, (62, 62, 64), -1)
    cv2.line(frame, (0, 365), (470, 352), (48, 58, 92), 30)
    cv2.line(frame, (70, 353), (450, 347), (95, 105, 125), 8)
    return frame


def _spoon_and_split_pen_frame() -> np.ndarray:
    frame = np.full((480, 640, 3), 235, dtype=np.uint8)
    cv2.line(frame, (0, 180), (300, 162), (76, 76, 78), 62)
    cv2.ellipse(frame, (405, 155), (105, 82), -5, 0, 360, (62, 62, 64), -1)
    cv2.line(frame, (35, 384), (400, 370), (48, 58, 92), 30)
    cv2.line(frame, (470, 344), (595, 342), (42, 42, 52), 28)
    cv2.line(frame, (70, 370), (585, 348), (118, 126, 140), 7)
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


def test_spoon_and_pen_stay_separate_when_one_loose_yolo_box_contains_both():
    decision = evaluate_foreground_multi_object_dispatch(
        _spoon_and_pen_frame(),
        roi=_roi(width=640, height=480),
        max_objects=1,
        min_area_ratio=0.003,
        reference_boxes=((0, 45, 525, 410),),
    )

    assert decision.allowed is False
    assert decision.object_count == 2
    assert decision.reason == "multiple waste types (2 visible objects)"


def test_spoon_and_split_pen_fragments_count_as_two_objects_not_three():
    decision = evaluate_foreground_multi_object_dispatch(
        _spoon_and_split_pen_frame(),
        roi=_roi(width=640, height=480),
        max_objects=1,
        min_area_ratio=0.003,
        reference_boxes=((0, 45, 610, 420),),
    )

    assert decision.allowed is False
    assert decision.object_count == 2
    assert decision.foreground_count >= 3


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


def test_two_foreground_objects_inside_one_loose_yolo_box_stay_blocked():
    decision = evaluate_foreground_multi_object_dispatch(
        _two_object_frame(),
        roi=_roi(),
        max_objects=1,
        min_area_ratio=0.002,
        reference_boxes=((20, 20, 285, 205),),
    )

    assert decision.allowed is False
    assert decision.object_count == 2
    assert decision.foreground_count == 2
    assert decision.reference_count == 1
    assert decision.unmatched_foreground_count == 0


def test_single_spoon_with_highlights_inside_one_yolo_box_stays_one_object():
    frame = np.full((260, 420, 3), 230, dtype=np.uint8)
    cv2.line(frame, (22, 174), (258, 142), (82, 82, 82), 34)
    cv2.line(frame, (22, 160), (258, 130), (168, 168, 166), 14)
    cv2.ellipse(frame, (312, 128), (74, 56), -8, 0, 360, (76, 76, 78), -1)
    cv2.ellipse(frame, (292, 122), (46, 28), -10, 0, 360, (168, 168, 166), -1)
    cv2.circle(frame, (330, 94), 12, (250, 250, 250), -1)

    decision = evaluate_foreground_multi_object_dispatch(
        frame,
        roi=_roi(width=420, height=260),
        max_objects=1,
        min_area_ratio=0.002,
        reference_boxes=((12, 55, 395, 205),),
    )

    assert decision.allowed is True
    assert decision.object_count == 1


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


def test_split_long_pen_without_reference_counts_as_one_object():
    frame = np.full((240, 420, 3), 245, dtype=np.uint8)
    frame[100:126, 36:178] = (35, 70, 180)
    frame[104:130, 210:372] = (44, 56, 112)

    decision = evaluate_foreground_multi_object_dispatch(
        frame,
        roi=_roi(width=420, height=240),
        max_objects=1,
        min_area_ratio=0.002,
    )

    assert decision.allowed is True
    assert decision.object_count == 1
    assert decision.foreground_count == 2


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
