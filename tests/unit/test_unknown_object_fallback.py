import numpy as np

from app.core.events import Detection
from app.core.unknown_object_fallback import UnknownObjectFallback


def test_static_contrast_fallback_detects_pen_like_object_inside_roi():
    frame = np.full((240, 320, 3), 235, dtype=np.uint8)
    frame[40:210, 150:165] = (190, 60, 30)
    roi = (80, 20, 180, 210)

    def in_roi(xyxy):
        x1, y1, x2, y2 = xyxy
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        return roi[0] <= cx <= roi[0] + roi[2] and roi[1] <= cy <= roi[1] + roi[3]

    fallback = UnknownObjectFallback()
    detections = [
        fallback.detect(
            frame,
            [],
            class_name="Unknown object",
            roi_filter=in_roi,
            min_raw_confidence=0.05,
            min_area_ratio=0.003,
            stable_frames=3,
            warmup_frames=6,
        )
        for _ in range(3)
    ]

    detected = detections[-1]
    assert detected is not None
    assert detected.cls_name == "Unknown object"
    assert detected.xyxy[0] <= 150 <= detected.xyxy[2]
    assert detected.xyxy[1] <= 40 <= detected.xyxy[3]


def test_transparent_edge_fallback_detects_crumpled_clear_plastic():
    import cv2

    frame = np.full((240, 320, 3), 238, dtype=np.uint8)
    cv2.ellipse(frame, (160, 126), (92, 72), 0, 0, 360, (205, 205, 205), 2)
    cv2.line(frame, (92, 84), (224, 162), (218, 218, 218), 2)
    cv2.line(frame, (102, 176), (242, 98), (210, 210, 210), 2)
    cv2.line(frame, (124, 54), (196, 202), (224, 224, 224), 2)

    fallback = UnknownObjectFallback()
    detections = [
        fallback.detect(
            frame,
            [],
            class_name="Unknown object",
            roi_filter=lambda _xyxy: True,
            min_raw_confidence=0.05,
            min_area_ratio=0.003,
            stable_frames=2,
            warmup_frames=6,
        )
        for _ in range(2)
    ]

    detected = detections[-1]
    assert detected is not None
    assert detected.source == "unknown_fallback:transparent_edges"
    assert detected.xyxy[0] < 160 < detected.xyxy[2]
    assert detected.xyxy[1] < 126 < detected.xyxy[3]


def test_low_conf_yolo_fallback_rejects_box_covering_the_tray():
    frame = np.full((240, 320, 3), 235, dtype=np.uint8)
    tray_sized_guess = Detection(0, "noise", 0.13, (2, 2, 318, 238))
    fallback = UnknownObjectFallback()

    detected = fallback.detect(
        frame,
        [tray_sized_guess],
        class_name="Unknown object",
        roi_filter=lambda _xyxy: True,
        min_raw_confidence=0.05,
        min_area_ratio=0.003,
        stable_frames=1,
        warmup_frames=6,
    )

    assert detected is None
