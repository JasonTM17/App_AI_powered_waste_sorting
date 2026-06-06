import numpy as np

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
