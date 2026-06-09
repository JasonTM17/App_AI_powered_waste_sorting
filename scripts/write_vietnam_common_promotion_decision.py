"""Write a candidate-only promotion decision for Vietnam common-waste training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

FOCUS_CLASSES = (
    "Pen",
    "Battery",
    "Toothbrush",
    "Textile",
    "Disposable tableware",
    "Unknown plastic",
    "Tetra pack",
    "Organic",
    "Aluminum can",
    "Plastic bottle",
)
REGRESSION_TOLERANCE = -0.02


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, action="append", required=True)
    parser.add_argument("--baseline", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    baselines = [_read_report(path) for path in args.baseline if path.exists()]
    best_baseline = max(
        baselines,
        key=lambda item: float(item.get("metrics", {}).get("metrics/mAP50-95(B)", 0.0)),
        default={},
    )
    candidates = [
        _candidate_summary(path, _read_report(path), best_baseline)
        for path in args.candidate
        if path.exists()
    ]
    selected = _select_candidate(candidates)
    selected_report = selected.get("report", {}) if selected else {}
    decision = {
        "promote": False,
        "reason": _decision_reason(selected),
        "candidate": str(selected.get("path", "")) if selected else "",
        "baseline": best_baseline.get("model", ""),
        "metrics": selected_report.get("metrics", {}),
        "focus_classes": _focus_class_metrics(selected_report),
        "regression_gate": selected.get("regression_gate", {}) if selected else {},
        "candidates": [_public_candidate_summary(item) for item in candidates],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Decision written to {args.out}")
    return 0


def _read_report(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _focus_class_metrics(report: dict) -> dict[str, object]:
    per_class = report.get("per_class", {})
    if not isinstance(per_class, dict):
        return {}
    return {name: per_class.get(name, {}) for name in FOCUS_CLASSES}


def _candidate_summary(path: Path, report: dict, baseline: dict) -> dict[str, object]:
    return {
        "path": str(path),
        "model": report.get("model", ""),
        "metrics": report.get("metrics", {}),
        "focus_classes": _focus_class_metrics(report),
        "regression_gate": _regression_gate(report, baseline),
        "score": _score(report),
        "report": report,
    }


def _select_candidate(candidates: list[dict[str, object]]) -> dict[str, object]:
    passing = [item for item in candidates if _gate_passed(item)]
    pool = passing or candidates
    return max(pool, key=lambda item: item.get("score", (0.0, 0.0)), default={})


def _gate_passed(item: dict[str, object]) -> bool:
    gate = item.get("regression_gate")
    return isinstance(gate, dict) and bool(gate.get("passed"))


def _public_candidate_summary(item: dict[str, object]) -> dict[str, object]:
    return {
        "path": item.get("path", ""),
        "model": item.get("model", ""),
        "metrics": item.get("metrics", {}),
        "focus_classes": item.get("focus_classes", {}),
        "regression_gate": item.get("regression_gate", {}),
    }


def _score(report: dict) -> tuple[float, float]:
    metrics = report.get("metrics", {})
    if not isinstance(metrics, dict):
        return (0.0, 0.0)
    return (
        float(metrics.get("metrics/mAP50-95(B)", 0.0)),
        float(metrics.get("metrics/mAP50(B)", 0.0)),
    )


def _decision_reason(selected: dict[str, object]) -> str:
    gate = selected.get("regression_gate", {}) if selected else {}
    if isinstance(gate, dict) and gate.get("passed"):
        return "Candidate only. Selected candidate passed regression gate; real camera and hardware gates are still required."
    return "Candidate only. No candidate passed regression gate; keep production model unchanged."


def _regression_gate(candidate: dict, baseline: dict) -> dict[str, object]:
    candidate_metrics = candidate.get("metrics", {})
    baseline_metrics = baseline.get("metrics", {})
    if not isinstance(candidate_metrics, dict) or not isinstance(baseline_metrics, dict):
        return {"passed": False, "reason": "missing_metrics"}
    deltas = {}
    passed = True
    for key in ("metrics/mAP50(B)", "metrics/mAP50-95(B)"):
        delta = float(candidate_metrics.get(key, 0.0)) - float(baseline_metrics.get(key, 0.0))
        deltas[key] = delta
        if delta < REGRESSION_TOLERANCE:
            passed = False
    return {"passed": passed, "deltas": deltas}


if __name__ == "__main__":
    raise SystemExit(main())
