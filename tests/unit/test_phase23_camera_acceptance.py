from __future__ import annotations

from scripts.run_three_bin_camera_acceptance import analyze_acceptance, bbox_in_roi

ROI = {"enabled": True, "x": 10, "y": 10, "width": 100, "height": 100}


def test_phase23_bbox_uses_center_point_roi():
    assert bbox_in_roi([20, 20, 40, 40], ROI) is True
    assert bbox_in_roi([120, 120, 150, 150], ROI) is False


def test_phase23_empty_tray_passes_without_in_roi_routes():
    samples = [
        {
            "estimated_frames": 100,
            "status": {"camera": {"running": True}},
            "detections": [],
        }
    ]

    result = analyze_acceptance(
        samples,
        scenario="empty",
        expected_command=None,
        roi=ROI,
        target_frames=100,
        min_observations=10,
        min_correct=9,
    )

    assert result["passed"] is True


def test_phase23_expected_bin_requires_nine_of_ten_routes():
    samples = [
        {
            "estimated_frames": idx + 1,
            "status": {"camera": {"running": True}},
            "detections": [
                {
                    "cls_name": "Kaggle 3-bin I",
                    "confidence": 0.91,
                    "bbox": [20, 20, 40, 40],
                    "uart_command": "I",
                    "source": "kaggle_three_bin_classifier",
                }
            ],
        }
        for idx in range(10)
    ]

    result = analyze_acceptance(
        samples,
        scenario="I",
        expected_command="I",
        roi=ROI,
        target_frames=100,
        min_observations=10,
        min_correct=9,
    )

    assert result["passed"] is True
    assert result["correct"] == 10
    assert result["sources"] == {"kaggle_three_bin_classifier": 10}


def test_phase23_multi_object_requires_multiple_waste_status():
    samples = [
        {
            "estimated_frames": 5,
            "status": {"camera": {"running": True}},
            "detections": [
                {
                    "cls_name": "Pen",
                    "confidence": 0.9,
                    "bbox": [20, 20, 40, 40],
                    "uart_command": "R",
                    "ack": "multiple waste types",
                },
                {
                    "cls_name": "Textile",
                    "confidence": 0.88,
                    "bbox": [50, 20, 70, 40],
                    "uart_command": "R",
                    "ack": "multiple waste types",
                },
            ],
        }
    ]

    result = analyze_acceptance(
        samples,
        scenario="multi_object",
        expected_command=None,
        roi=ROI,
        target_frames=100,
        min_observations=1,
        min_correct=1,
    )

    assert result["passed"] is True
    assert result["blocked_sample_count"] == 1
