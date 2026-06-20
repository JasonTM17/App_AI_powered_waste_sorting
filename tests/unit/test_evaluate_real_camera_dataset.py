from __future__ import annotations

from argparse import Namespace

from scripts.evaluate_real_camera_dataset import _predictions, _route_eval, runtime_thresholds


def test_route_eval_counts_same_bin_as_correct_even_when_class_differs() -> None:
    gts = [{"class_name": "Plastic bottle", "xyxy": (0.0, 0.0, 100.0, 100.0)}]
    preds = [{"class_name": "Aluminum can", "conf": 0.8, "xyxy": (0.0, 0.0, 100.0, 100.0)}]

    route = _route_eval(gts, preds, iou_threshold=0.5)

    assert route["counts"]["tp"] == 1
    assert not route["confusions"]


def test_route_eval_flags_dangerous_bin_confusion() -> None:
    gts = [{"class_name": "Plastic bottle", "xyxy": (0.0, 0.0, 100.0, 100.0)}]
    preds = [{"class_name": "Organic", "conf": 0.8, "xyxy": (0.0, 0.0, 100.0, 100.0)}]

    route = _route_eval(gts, preds, iou_threshold=0.5)

    assert route["counts"]["fp"] == 1
    assert route["counts"]["fn"] == 1
    assert route["confusions"]["I->O"] == 1


def test_predictions_apply_runtime_class_thresholds() -> None:
    class _Xyxy:
        def tolist(self) -> list[float]:
            return [0.0, 0.0, 10.0, 10.0]

    class _Box:
        def __init__(self, cls_id: int, conf: float):
            self.cls = [cls_id]
            self.conf = [conf]
            self.xyxy = [_Xyxy()]

    class _Result:
        boxes = [_Box(24, 0.32), _Box(42, 0.32)]

    rows = _predictions(
        _Result(),
        {24: "Plastic bottle", 42: "Pen"},
        thresholds={"*": 0.4, "Plastic bottle": 0.3},
    )

    assert [row["class_name"] for row in rows] == ["Plastic bottle"]


def test_runtime_thresholds_disabled_returns_empty() -> None:
    args = Namespace(runtime_thresholds=False, config=None)

    assert runtime_thresholds(args) == {}
