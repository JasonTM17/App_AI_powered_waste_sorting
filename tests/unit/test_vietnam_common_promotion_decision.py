from __future__ import annotations

import json
from pathlib import Path

from scripts.write_vietnam_common_promotion_decision import main


def _write_eval(path: Path, map50: float, map5095: float, *, model: str = "") -> None:
    path.write_text(
        json.dumps(
            {
                "model": model or str(path.with_suffix(".pt")),
                "metrics": {
                    "metrics/mAP50(B)": map50,
                    "metrics/mAP50-95(B)": map5095,
                },
                "per_class": {
                    "Pen": {
                        "class_id": 42,
                        "precision": 0.9,
                        "recall": 0.8,
                        "map50": 0.7,
                        "map50_95": 0.6,
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_decision_selects_best_passing_candidate(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    stage_a = tmp_path / "stage-a.json"
    stage_b = tmp_path / "stage-b.json"
    out = tmp_path / "decision.json"
    _write_eval(baseline, 0.64, 0.50)
    _write_eval(stage_a, 0.63, 0.49)
    _write_eval(stage_b, 0.55, 0.42)

    monkeypatch.setattr(
        "sys.argv",
        [
            "write_vietnam_common_promotion_decision.py",
            "--candidate",
            str(stage_a),
            "--candidate",
            str(stage_b),
            "--baseline",
            str(baseline),
            "--out",
            str(out),
        ],
    )

    assert main() == 0
    decision = json.loads(out.read_text(encoding="utf-8"))
    assert decision["promote"] is False
    assert decision["candidate"] == str(stage_a)
    assert decision["regression_gate"]["passed"] is True
    assert len(decision["candidates"]) == 2


def test_decision_keeps_production_when_all_candidates_regress(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    stage_a = tmp_path / "stage-a.json"
    out = tmp_path / "decision.json"
    _write_eval(baseline, 0.64, 0.50)
    _write_eval(stage_a, 0.55, 0.42)

    monkeypatch.setattr(
        "sys.argv",
        [
            "write_vietnam_common_promotion_decision.py",
            "--candidate",
            str(stage_a),
            "--baseline",
            str(baseline),
            "--out",
            str(out),
        ],
    )

    assert main() == 0
    decision = json.loads(out.read_text(encoding="utf-8"))
    assert decision["promote"] is False
    assert decision["candidate"] == str(stage_a)
    assert decision["regression_gate"]["passed"] is False
    assert "No candidate passed" in decision["reason"]
