from typing import ClassVar

from scripts.evaluate_yolo import _per_class_metrics


class _BoxMetrics:
    ap_class_index: ClassVar[list[int]] = [42, 44]

    @staticmethod
    def class_result(index):
        return [
            (0.91, 0.88, 0.93, 0.71),
            (0.83, 0.79, 0.86, 0.62),
        ][index]


class _Metrics:
    box = _BoxMetrics()
    names: ClassVar[dict[int, str]] = {42: "Pen", 44: "Toothbrush"}


def test_per_class_metrics_uses_ap_class_index():
    report = _per_class_metrics(_Metrics())

    assert report["Pen"] == {
        "class_id": 42,
        "precision": 0.91,
        "recall": 0.88,
        "map50": 0.93,
        "map50_95": 0.71,
    }
    assert report["Toothbrush"]["class_id"] == 44
