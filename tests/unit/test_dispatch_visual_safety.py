import cv2
import numpy as np

from app.core.dispatch_visual_safety import evaluate_dispatch_visual_safety


def _sharp_object_frame() -> np.ndarray:
    frame = np.full((240, 320, 3), 238, dtype=np.uint8)
    cv2.rectangle(frame, (55, 88), (265, 150), (20, 70, 170), -1)
    for x in range(65, 255, 12):
        cv2.line(frame, (x, 94), (x, 144), (245, 245, 245), 2)
    return frame


def test_visual_safety_rejects_near_full_frame_box() -> None:
    decision = evaluate_dispatch_visual_safety(
        _sharp_object_frame(),
        (2, 2, 318, 238),
        max_bbox_area_ratio=0.82,
        min_sharpness=24.0,
    )

    assert decision.allowed is False
    assert decision.reason == "object framing invalid"
    assert decision.area_ratio > 0.95


def test_visual_safety_rejects_blurry_evidence() -> None:
    blurred = cv2.GaussianBlur(_sharp_object_frame(), (41, 41), 0)
    decision = evaluate_dispatch_visual_safety(
        blurred,
        (55, 88, 265, 150),
        max_bbox_area_ratio=0.82,
        min_sharpness=24.0,
    )

    assert decision.allowed is False
    assert decision.reason == "camera blurry"
    assert decision.sharpness < 24.0


def test_visual_safety_allows_blurry_evidence_when_sharpness_guard_is_disabled() -> None:
    blurred = cv2.GaussianBlur(_sharp_object_frame(), (41, 41), 0)
    decision = evaluate_dispatch_visual_safety(
        blurred,
        (55, 88, 265, 150),
        max_bbox_area_ratio=0.82,
        min_sharpness=0.0,
    )

    assert decision.allowed is True
    assert decision.reason == "ready"


def test_visual_safety_allows_sharp_well_framed_object() -> None:
    decision = evaluate_dispatch_visual_safety(
        _sharp_object_frame(),
        (55, 88, 265, 150),
        max_bbox_area_ratio=0.82,
        min_sharpness=24.0,
    )

    assert decision.allowed is True
    assert decision.reason == "ready"
    assert decision.area_ratio < 0.2
    assert decision.sharpness >= 24.0
