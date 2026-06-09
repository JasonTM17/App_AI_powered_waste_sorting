from __future__ import annotations

import json
from pathlib import Path

from scripts.write_weak_recovery_decision import main


def _write_eval(
    path: Path,
    map50: float,
    map5095: float,
    *,
    pen: float,
    battery: float,
    disposable: float = 0.0,
    ceramic: float = 0.0,
    electronics: float = 0.0,
    disposable_recall: float = 0.0,
    ceramic_recall: float = 0.0,
    electronics_recall: float = 0.0,
) -> None:
    path.write_text(
        json.dumps(
            {
                "model": str(path.with_suffix(".pt")),
                "metrics": {
                    "metrics/mAP50(B)": map50,
                    "metrics/mAP50-95(B)": map5095,
                },
                "per_class": {
                    "Pen": {"map50": pen, "map50_95": pen / 2, "recall": pen},
                    "Battery": {"map50": battery, "map50_95": battery / 2, "recall": battery},
                    "Disposable tableware": {
                        "map50": disposable,
                        "map50_95": disposable / 2,
                        "recall": disposable_recall,
                    },
                    "Ceramic": {
                        "map50": ceramic,
                        "map50_95": ceramic / 2,
                        "recall": ceramic_recall,
                    },
                    "Electronics": {
                        "map50": electronics,
                        "map50_95": electronics / 2,
                        "recall": electronics_recall,
                    },
                    "Unknown plastic": {"map50": 0.01, "map50_95": 0.005},
                },
            }
        ),
        encoding="utf-8",
    )


def test_weak_recovery_decision_allows_stage_b_when_gates_pass(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    weak_baseline = tmp_path / "phase13.json"
    stage_a = tmp_path / "stage-a.json"
    out = tmp_path / "decision.json"
    _write_eval(baseline, 0.64, 0.50, pen=0.30, battery=0.30)
    _write_eval(weak_baseline, 0.40, 0.30, pen=0.20, battery=0.20)
    _write_eval(stage_a, 0.63, 0.49, pen=0.25, battery=0.28)

    monkeypatch.setattr(
        "sys.argv",
        [
            "write_weak_recovery_decision.py",
            "--candidate",
            str(stage_a),
            "--baseline",
            str(baseline),
            "--weak-baseline",
            str(weak_baseline),
            "--out",
            str(out),
        ],
    )

    assert main() == 0
    decision = json.loads(out.read_text(encoding="utf-8"))
    assert decision["promote"] is False
    assert decision["stage_b_allowed"] is True
    assert decision["weak_class_gate"]["improved_count"] >= 2


def test_weak_recovery_decision_blocks_stage_b_without_weak_improvements(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    weak_baseline = tmp_path / "phase13.json"
    stage_a = tmp_path / "stage-a.json"
    out = tmp_path / "decision.json"
    _write_eval(baseline, 0.64, 0.50, pen=0.30, battery=0.30)
    _write_eval(weak_baseline, 0.40, 0.30, pen=0.25, battery=0.25)
    _write_eval(stage_a, 0.63, 0.49, pen=0.20, battery=0.28)

    monkeypatch.setattr(
        "sys.argv",
        [
            "write_weak_recovery_decision.py",
            "--candidate",
            str(stage_a),
            "--baseline",
            str(baseline),
            "--weak-baseline",
            str(weak_baseline),
            "--out",
            str(out),
        ],
    )

    assert main() == 0
    decision = json.loads(out.read_text(encoding="utf-8"))
    assert decision["stage_b_allowed"] is False
    assert decision["weak_class_gate"]["passed"] is False
    assert "Stage B blocked" in decision["reason"]


def test_decision_blocks_when_required_weak_class_does_not_improve(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    weak_baseline = tmp_path / "phase14.json"
    stage_a = tmp_path / "stage-a.json"
    out = tmp_path / "decision.json"
    _write_eval(baseline, 0.64, 0.50, pen=0.20, battery=0.20, disposable=0.10, ceramic=0.10)
    _write_eval(weak_baseline, 0.40, 0.30, pen=0.20, battery=0.20, disposable=0.10, ceramic=0.10)
    _write_eval(stage_a, 0.63, 0.49, pen=0.30, battery=0.28, disposable=0.09, ceramic=0.20)

    monkeypatch.setattr(
        "sys.argv",
        [
            "write_weak_recovery_decision.py",
            "--candidate",
            str(stage_a),
            "--baseline",
            str(baseline),
            "--weak-baseline",
            str(weak_baseline),
            "--required-weak-class",
            "Pen",
            "--required-weak-class",
            "Disposable tableware",
            "--required-weak-class",
            "Ceramic",
            "--out",
            str(out),
        ],
    )

    assert main() == 0
    decision = json.loads(out.read_text(encoding="utf-8"))
    assert decision["stage_b_allowed"] is False
    assert decision["weak_class_gate"]["missing_required_improvements"] == ["Disposable tableware"]


def test_decision_blocks_when_required_recall_is_not_practical(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    weak_baseline = tmp_path / "phase15.json"
    stage_a = tmp_path / "stage-a.json"
    out = tmp_path / "decision.json"
    _write_eval(
        baseline,
        0.64,
        0.50,
        pen=0.20,
        battery=0.20,
        disposable=0.10,
        ceramic=0.10,
        electronics=0.10,
    )
    _write_eval(
        weak_baseline,
        0.40,
        0.30,
        pen=0.20,
        battery=0.20,
        disposable=0.05,
        ceramic=0.05,
        electronics=0.05,
    )
    _write_eval(
        stage_a,
        0.63,
        0.49,
        pen=0.30,
        battery=0.28,
        disposable=0.20,
        ceramic=0.20,
        electronics=0.20,
        disposable_recall=0.10,
        ceramic_recall=0.00,
        electronics_recall=0.10,
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "write_weak_recovery_decision.py",
            "--candidate",
            str(stage_a),
            "--baseline",
            str(baseline),
            "--weak-baseline",
            str(weak_baseline),
            "--required-recall-class",
            "Disposable tableware",
            "--required-recall-class",
            "Ceramic",
            "--required-recall-class",
            "Electronics",
            "--min-required-recall",
            "0.05",
            "--out",
            str(out),
        ],
    )

    assert main() == 0
    decision = json.loads(out.read_text(encoding="utf-8"))
    assert decision["stage_b_allowed"] is False
    assert decision["recall_gate"]["missing"] == ["Ceramic"]
