"""Write the Phase 14 candidate-only weak recovery decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

WEAK_CLASSES = (
    "Pen",
    "Battery",
    "Toothbrush",
    "Textile",
    "Disposable tableware",
    "Unknown plastic",
    "Tetra pack",
    "Ceramic",
    "Aerosols",
    "Electronics",
)
REGRESSION_TOLERANCE = -0.02


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, action="append", required=True)
    parser.add_argument("--baseline", type=Path, action="append", default=[])
    parser.add_argument("--weak-baseline", type=Path, required=True)
    parser.add_argument("--comparison-baseline", type=Path, action="append", default=[])
    parser.add_argument("--required-weak-class", action="append", default=[])
    parser.add_argument("--required-recall-class", action="append", default=[])
    parser.add_argument("--min-required-recall", type=float, default=0.05)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--min-weak-improvements", type=int, default=2)
    args = parser.parse_args()

    baseline = _best_baseline([_read(path) for path in args.baseline if path.exists()])
    weak_baseline = _read(args.weak_baseline)
    required_classes = tuple(str(name) for name in args.required_weak_class)
    required_recall_classes = tuple(str(name) for name in args.required_recall_class)
    candidates = [
        _candidate_summary(
            path,
            _read(path),
            baseline,
            weak_baseline,
            args.min_weak_improvements,
            required_classes,
            required_recall_classes,
            args.min_required_recall,
        )
        for path in args.candidate
        if path.exists()
    ]
    selected = _select_candidate(candidates)
    selected_report = selected.get("report", {}) if selected else {}
    decision = {
        "promote": False,
        "stage_b_allowed": _stage_b_allowed(selected),
        "reason": _decision_reason(selected),
        "candidate": str(selected.get("path", "")) if selected else "",
        "baseline": baseline.get("model", ""),
        "weak_baseline": str(args.weak_baseline),
        "metrics": selected_report.get("metrics", {}),
        "weak_classes": _weak_metrics(selected_report),
        "regression_gate": selected.get("regression_gate", {}) if selected else {},
        "weak_class_gate": selected.get("weak_class_gate", {}) if selected else {},
        "recall_gate": selected.get("recall_gate", {}) if selected else {},
        "comparisons": _comparison_summaries(selected_report, args.comparison_baseline),
        "candidates": [_public_summary(item) for item in candidates],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Weak recovery decision written to {args.out}")
    return 0


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _best_baseline(reports: list[dict[str, Any]]) -> dict[str, Any]:
    return max(reports, key=lambda report: _score(report), default={})


def _candidate_summary(
    path: Path,
    report: dict[str, Any],
    baseline: dict[str, Any],
    weak_baseline: dict[str, Any],
    min_weak_improvements: int,
    required_classes: tuple[str, ...],
    required_recall_classes: tuple[str, ...],
    min_required_recall: float,
) -> dict[str, Any]:
    return {
        "path": str(path),
        "model": report.get("model", ""),
        "metrics": report.get("metrics", {}),
        "weak_classes": _weak_metrics(report),
        "regression_gate": _regression_gate(report, baseline),
        "weak_class_gate": _weak_class_gate(
            report,
            weak_baseline,
            min_weak_improvements,
            required_classes,
        ),
        "recall_gate": _recall_gate(
            report,
            weak_baseline,
            required_recall_classes,
            min_required_recall,
        ),
        "score": _score(report),
        "report": report,
    }


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [item for item in candidates if _stage_b_allowed(item)]
    return max(passing or candidates, key=lambda item: item.get("score", (0.0, 0.0)), default={})


def _stage_b_allowed(item: dict[str, Any]) -> bool:
    regression = item.get("regression_gate", {})
    weak = item.get("weak_class_gate", {})
    recall = item.get("recall_gate", {})
    recall_passed = not recall or bool(isinstance(recall, dict) and recall.get("passed"))
    return bool(isinstance(regression, dict) and regression.get("passed")) and bool(
        isinstance(weak, dict) and weak.get("passed")
    ) and recall_passed


def _public_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": item.get("path", ""),
        "model": item.get("model", ""),
        "metrics": item.get("metrics", {}),
        "weak_classes": item.get("weak_classes", {}),
        "regression_gate": item.get("regression_gate", {}),
        "weak_class_gate": item.get("weak_class_gate", {}),
        "recall_gate": item.get("recall_gate", {}),
    }


def _score(report: dict[str, Any]) -> tuple[float, float]:
    metrics = report.get("metrics", {})
    if not isinstance(metrics, dict):
        return (0.0, 0.0)
    return (
        float(metrics.get("metrics/mAP50-95(B)", 0.0)),
        float(metrics.get("metrics/mAP50(B)", 0.0)),
    )


def _regression_gate(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    candidate_metrics = candidate.get("metrics", {})
    baseline_metrics = baseline.get("metrics", {})
    if not isinstance(candidate_metrics, dict) or not isinstance(baseline_metrics, dict):
        return {"passed": False, "reason": "missing_metrics"}
    deltas: dict[str, float] = {}
    passed = True
    for key in ("metrics/mAP50(B)", "metrics/mAP50-95(B)"):
        delta = float(candidate_metrics.get(key, 0.0)) - float(baseline_metrics.get(key, 0.0))
        deltas[key] = delta
        passed = passed and delta >= REGRESSION_TOLERANCE
    return {"passed": passed, "deltas": deltas}


def _weak_class_gate(
    candidate: dict[str, Any],
    weak_baseline: dict[str, Any],
    min_weak_improvements: int,
    required_classes: tuple[str, ...] = (),
) -> dict[str, Any]:
    candidate_metrics = _weak_metrics(candidate)
    baseline_metrics = _weak_metrics(weak_baseline)
    improvements = {}
    improved = 0
    for class_name in WEAK_CLASSES:
        current = candidate_metrics.get(class_name, {})
        prior = baseline_metrics.get(class_name, {})
        current_map50 = float(current.get("map50", 0.0)) if isinstance(current, dict) else 0.0
        prior_map50 = float(prior.get("map50", 0.0)) if isinstance(prior, dict) else 0.0
        delta = current_map50 - prior_map50
        improved += int(delta > 0.0)
        improvements[class_name] = {
            "candidate_map50": current_map50,
            "baseline_map50": prior_map50,
            "delta_map50": delta,
        }
    missing_required = [
        class_name
        for class_name in required_classes
        if improvements.get(class_name, {}).get("delta_map50", 0.0) <= 0.0
    ]
    return {
        "passed": improved >= min_weak_improvements and not missing_required,
        "improved_count": improved,
        "required": min_weak_improvements,
        "required_classes": list(required_classes),
        "missing_required_improvements": missing_required,
        "improvements": improvements,
    }


def _weak_metrics(report: dict[str, Any]) -> dict[str, Any]:
    per_class = report.get("per_class")
    if not isinstance(per_class, dict):
        per_class = report.get("focus_classes")
    if not isinstance(per_class, dict):
        return {}
    return {name: per_class.get(name, {}) for name in WEAK_CLASSES}


def _recall_gate(
    candidate: dict[str, Any],
    weak_baseline: dict[str, Any],
    required_classes: tuple[str, ...],
    min_required_recall: float,
) -> dict[str, Any]:
    if not required_classes:
        return {}
    candidate_metrics = _weak_metrics(candidate)
    baseline_metrics = _weak_metrics(weak_baseline)
    rows = {}
    missing = []
    for class_name in required_classes:
        current = candidate_metrics.get(class_name, {})
        prior = baseline_metrics.get(class_name, {})
        current_recall = float(current.get("recall", 0.0)) if isinstance(current, dict) else 0.0
        prior_recall = float(prior.get("recall", 0.0)) if isinstance(prior, dict) else 0.0
        delta = current_recall - prior_recall
        rows[class_name] = {
            "candidate_recall": current_recall,
            "baseline_recall": prior_recall,
            "delta_recall": delta,
            "min_required_recall": min_required_recall,
        }
        if current_recall < min_required_recall or delta <= 0.0:
            missing.append(class_name)
    return {"passed": not missing, "required_classes": list(required_classes), "missing": missing, "classes": rows}


def _decision_reason(selected: dict[str, Any]) -> str:
    if _stage_b_allowed(selected):
        return "Candidate only. Stage A passed regression and weak-class gates; Stage B may run."
    return "Candidate only. Stage B blocked; keep production model unchanged."


def _comparison_summaries(selected_report: dict[str, Any], paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        if not path.exists():
            continue
        report = _read(path)
        rows.append(
            {
                "path": str(path),
                "metric_deltas": _metric_deltas(selected_report, report),
                "weak_deltas": _weak_deltas(selected_report, report),
            }
        )
    return rows


def _metric_deltas(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, float]:
    candidate_metrics = candidate.get("metrics", {})
    baseline_metrics = baseline.get("metrics", {})
    if not isinstance(candidate_metrics, dict) or not isinstance(baseline_metrics, dict):
        return {}
    return {
        key: float(candidate_metrics.get(key, 0.0)) - float(baseline_metrics.get(key, 0.0))
        for key in ("metrics/mAP50(B)", "metrics/mAP50-95(B)")
    }


def _weak_deltas(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, float]:
    candidate_classes = _weak_metrics(candidate)
    baseline_classes = _weak_metrics(baseline)
    deltas = {}
    for class_name in WEAK_CLASSES:
        current = candidate_classes.get(class_name, {})
        prior = baseline_classes.get(class_name, {})
        current_map50 = float(current.get("map50", 0.0)) if isinstance(current, dict) else 0.0
        prior_map50 = float(prior.get("map50", 0.0)) if isinstance(prior, dict) else 0.0
        deltas[class_name] = current_map50 - prior_map50
    return deltas


if __name__ == "__main__":
    raise SystemExit(main())
