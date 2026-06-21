from scripts.evaluate_history_captures import _iou, select_prediction


def test_select_prediction_prefers_box_matching_history_object():
    candidates = [
        {"class_name": "Pen", "confidence": 0.95, "bbox": [200, 200, 300, 300]},
        {"class_name": "Iron utensils", "confidence": 0.70, "bbox": [10, 10, 110, 110]},
    ]

    selected = select_prediction(candidates, [0, 0, 120, 120])

    assert selected["class_name"] == "Iron utensils"


def test_select_prediction_uses_confidence_without_history_bbox():
    candidates = [
        {"class_name": "Pen", "confidence": 0.80, "bbox": [0, 0, 10, 10]},
        {"class_name": "Paper", "confidence": 0.60, "bbox": [0, 0, 20, 20]},
    ]

    assert select_prediction(candidates, None)["class_name"] == "Pen"
    assert select_prediction([], None) == {}


def test_iou_handles_overlap_and_disjoint_boxes():
    assert _iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert _iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0
