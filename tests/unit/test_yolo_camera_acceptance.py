from scripts import run_yolo_camera_acceptance as runner
from scripts.run_yolo_camera_acceptance import analyze_yolo_acceptance

ROI = {"enabled": True, "x": 0, "y": 0, "width": 100, "height": 100}


def test_yolo_camera_health_requires_non_black_diagnostics():
    samples = [
        {
            "estimated_frames": 30,
            "status": {
                "camera": {"running": True},
                "camera_diagnostics": {"usable": True, "black_frame": False},
            },
            "detections": [],
        }
    ]

    result = analyze_yolo_acceptance(
        samples,
        scenario="camera_health",
        expected_command=None,
        roi=ROI,
        target_frames=30,
        min_observations=10,
        min_correct=9,
    )

    assert result["passed"] is True


def test_yolo_acceptance_uses_uart_command_not_three_bin_class_name():
    samples = [
        {
            "estimated_frames": 1,
            "status": {"camera": {"running": True}},
            "detections": [
                {
                    "cls_name": "O: Organic",
                    "confidence": 0.9,
                    "bbox": [10, 10, 20, 20],
                    "uart_command": "",
                    "source": "YOLO",
                }
            ],
        }
    ]

    result = analyze_yolo_acceptance(
        samples,
        scenario="O",
        expected_command="O",
        roi=ROI,
        target_frames=1,
        min_observations=1,
        min_correct=1,
    )

    assert result["passed"] is False
    assert result["observations"] == 0


def test_yolo_acceptance_expected_class_blocks_route_only_pass():
    samples = [
        {
            "estimated_frames": 10,
            "status": {"camera": {"running": True}},
            "detections": [
                {
                    "cls_name": "Unknown object",
                    "confidence": 0.39,
                    "bbox": [10, 10, 80, 20],
                    "uart_command": "R",
                    "source": "YOLO",
                }
            ],
        }
        for _ in range(10)
    ]

    result = analyze_yolo_acceptance(
        samples,
        scenario="R",
        expected_command="R",
        expected_class="Pen",
        roi=ROI,
        target_frames=10,
        min_observations=10,
        min_correct=9,
    )

    assert result["passed"] is False
    assert result["route_correct"] == 10
    assert result["correct"] == 0
    assert result["classes"] == {"Unknown object": 10}


def test_yolo_acceptance_expected_class_passes_when_label_matches():
    samples = [
        {
            "estimated_frames": 10,
            "status": {"camera": {"running": True}},
            "detections": [
                {
                    "cls_name": "Pen",
                    "confidence": 0.91,
                    "bbox": [10, 10, 80, 20],
                    "uart_command": "R",
                    "source": "manual_reference",
                }
            ],
        }
        for _ in range(10)
    ]

    result = analyze_yolo_acceptance(
        samples,
        scenario="R",
        expected_command="R",
        expected_class="Pen",
        roi=ROI,
        target_frames=10,
        min_observations=10,
        min_correct=9,
    )

    assert result["passed"] is True
    assert result["correct"] == 10
    assert result["classes"] == {"Pen": 10}


def test_collect_live_samples_records_timeout_as_evidence(monkeypatch):
    def raise_timeout(*_args, **_kwargs):
        raise TimeoutError("timed out in 0.8s")

    fallback_status = {
        "camera": {"running": False},
        "camera_diagnostics": {"usable": False, "reason": "black frame"},
    }
    monkeypatch.setattr(runner, "_collect_live_samples_base", raise_timeout)

    samples = runner._collect_live_samples(
        "http://127.0.0.1:8765",
        "token",
        target_frames=30,
        max_seconds=1.0,
        fallback_status=fallback_status,
    )

    assert samples[0]["estimated_frames"] == 0
    assert samples[0]["status"] == fallback_status
    assert "TimeoutError" in samples[0]["error"]
