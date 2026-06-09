"""Run camera-only acceptance for the current YOLO model."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import httpx

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_three_bin_camera_acceptance import (
    _collect_live_samples as _collect_live_samples_base,
)
from scripts.run_three_bin_camera_acceptance import (
    _count_values,
    _get_json,
    _post_json,
    _put_json,
    _redact_evidence,
    _resolve_token,
    bbox_in_roi,
)

REPORT_DIR = ROOT / "runs" / "eval"


def main() -> int:
    _configure_console_utf8()
    args = _parser().parse_args()
    report = run_acceptance(args)
    path = _write_report(report, args.out)
    analysis = report.get("analysis", {})
    print(f"YOLO camera report: {path}")
    print(f"Scenario: {report.get('scenario')} pass={analysis.get('passed')}")
    print(f"Reason: {analysis.get('reason', '')}")
    return 0 if analysis.get("passed") else 2


def run_acceptance(args: argparse.Namespace) -> dict[str, Any]:
    report: dict[str, Any] = {
        "phase": "camera_yolo_acceptance",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario": args.scenario,
        "expected_command": _expected_command(args.scenario, args.expected),
        "expected_class": args.expected_class,
        "target_frames": args.frames,
        "min_observations": args.min_observations,
        "min_correct": args.min_correct,
        "safety": {
            "actuation_forced_off": True,
            "hardware_dispatch_expected": False,
            "three_bin_classifier_expected": False,
            "models_best_unchanged_check": str(ROOT / "models" / "best.pt"),
        },
        "samples": [],
    }
    with httpx.Client(timeout=args.http_timeout) as client:
        token = _resolve_token(client, args)
        headers = {"Authorization": f"Bearer {token}"}
        report["status_before"] = _get_json(
            client,
            args.agent_url,
            "/api/status?include_devices=true",
            headers,
        )
        report["actuation_before"] = _redact_evidence(
            _get_json(client, args.agent_url, "/api/actuation/test-mode", headers)
        )
        _put_json(client, args.agent_url, "/api/actuation/test-mode", headers, {"enabled": False})
        settings = _get_json(client, args.agent_url, "/api/settings", headers)
        config = cast(dict[str, Any], settings.get("config") or {})
        report["test_config"] = _summarize_config(config)
        if bool((config.get("three_bin_classifier") or {}).get("enabled")):
            report["analysis"] = {
                "passed": False,
                "reason": "three_bin_classifier is enabled; disable it for YOLO camera acceptance",
            }
            return report

        if args.start_camera:
            report["camera_start"] = _post_json(client, args.agent_url, "/api/camera/start", headers, {})
            time.sleep(args.camera_warmup_seconds)

        status_after_setup = _get_json(
            client,
            args.agent_url,
            "/api/status?include_devices=true",
            headers,
        )
        report["status_after_setup"] = status_after_setup
        roi = (config.get("roi") or {}) if isinstance(config, dict) else {}
        if args.scenario == "camera_health":
            report["samples"] = _collect_live_samples(
                args.agent_url,
                token,
                target_frames=args.frames,
                max_seconds=args.max_seconds,
                fallback_status=status_after_setup,
            )
        elif not status_after_setup.get("camera", {}).get("running"):
            report["analysis"] = {
                "passed": False,
                "reason": "camera is not running; cannot execute YOLO camera acceptance",
            }
            return report
        else:
            report["samples"] = _collect_live_samples(
                args.agent_url,
                token,
                target_frames=args.frames,
                max_seconds=args.max_seconds,
                fallback_status=status_after_setup,
            )
        report["analysis"] = analyze_yolo_acceptance(
            report["samples"],
            scenario=args.scenario,
            expected_command=report["expected_command"],
            roi=roi,
            target_frames=args.frames,
            min_observations=args.min_observations,
            min_correct=args.min_correct,
            expected_class=args.expected_class,
        )
        report["actuation_after"] = _redact_evidence(
            _get_json(client, args.agent_url, "/api/actuation/test-mode", headers)
        )
    return report


def _collect_live_samples(
    agent_url: str,
    token: str,
    *,
    target_frames: int,
    max_seconds: float,
    fallback_status: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    try:
        return _collect_live_samples_base(
            agent_url,
            token,
            target_frames=target_frames,
            max_seconds=max_seconds,
        )
    except Exception as exc:
        return [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "estimated_frames": 0,
                "status": fallback_status or {},
                "detections": [],
                "error": f"{type(exc).__name__}: {exc}",
            }
        ]


def analyze_yolo_acceptance(
    samples: list[dict[str, Any]],
    *,
    scenario: str,
    expected_command: str | None,
    roi: dict[str, Any],
    target_frames: int,
    min_observations: int,
    min_correct: int,
    expected_class: str = "",
) -> dict[str, Any]:
    annotated = [_annotate_sample(sample, roi) for sample in samples]
    estimated_frames = max((int(sample.get("estimated_frames") or 0) for sample in annotated), default=0)
    camera_running = any(bool(sample.get("status", {}).get("camera", {}).get("running")) for sample in annotated)
    diagnostics = [
        sample.get("status", {}).get("camera_diagnostics") or {}
        for sample in annotated
        if isinstance(sample.get("status"), dict)
    ]
    usable_diagnostics = [
        item
        for item in diagnostics
        if bool(item.get("usable")) and not bool(item.get("black_frame"))
    ]
    if scenario == "camera_health":
        passed = camera_running and estimated_frames >= target_frames and bool(usable_diagnostics)
        return {
            "passed": passed,
            "reason": "camera health passed" if passed else "camera needs valid non-black frames",
            "estimated_frames": estimated_frames,
            "latest_diagnostics": diagnostics[-1] if diagnostics else {},
        }

    in_roi_detections = [
        det
        for sample in annotated
        for det in sample.get("detections", [])
        if det.get("in_roi")
    ]
    routed_in_roi = [det for det in in_roi_detections if det.get("command")]
    if scenario == "empty":
        passed = camera_running and estimated_frames >= target_frames and not routed_in_roi
        return {
            "passed": passed,
            "reason": (
                "empty tray had no in-ROI route"
                if passed
                else "empty tray still needs frames with no in-ROI route"
            ),
            "estimated_frames": estimated_frames,
            "false_routes": routed_in_roi[:10],
        }
    if scenario in {"O", "R", "I"}:
        observations = _best_routed_observations(annotated)
        route_correct = [det for det in observations if det.get("command") == expected_command]
        clean_expected_class = expected_class.strip()
        correct = [
            det
            for det in route_correct
            if not clean_expected_class or str(det.get("cls_name") or "") == clean_expected_class
        ]
        reason = f"need at least {min_correct}/{min_observations} correct {expected_command} routes"
        if clean_expected_class:
            reason += f" with class {clean_expected_class}"
        return {
            "passed": len(observations) >= min_observations and len(correct) >= min_correct,
            "reason": reason,
            "observations": len(observations),
            "correct": len(correct),
            "route_correct": len(route_correct),
            "expected_class": clean_expected_class,
            "commands": _count_values(det.get("command") for det in observations),
            "classes": _count_values(det.get("cls_name") for det in observations),
            "sources": _count_values(det.get("source") for det in observations),
            "examples": observations[:10],
        }
    if scenario == "outside_roi":
        outside_routed = [
            det
            for sample in annotated
            for det in sample.get("detections", [])
            if det.get("command") and not det.get("in_roi")
        ]
        unsafe_inside = [det for det in routed_in_roi if det.get("command")]
        return {
            "passed": len(outside_routed) >= min_observations and not unsafe_inside,
            "reason": "outside ROI must not create an in-ROI route",
            "outside_observations": len(outside_routed),
            "unsafe_inside_routes": unsafe_inside[:10],
        }
    if scenario == "multi_object":
        multi_samples = []
        blocked_samples = []
        for sample in annotated:
            classes = {
                str(det.get("cls_name") or "")
                for det in sample.get("detections", [])
                if det.get("in_roi") and det.get("cls_name")
            }
            if len(classes) < 2:
                continue
            multi_samples.append({"timestamp": sample.get("timestamp"), "classes": sorted(classes)})
            if any(
                str(det.get("ack") or "").lower() == "multiple waste types"
                for det in sample.get("detections", [])
                if det.get("in_roi")
            ):
                blocked_samples.append(sample)
        return {
            "passed": bool(multi_samples) and bool(blocked_samples),
            "reason": "multi-object scene must warn and block",
            "multi_samples": multi_samples[:10],
            "blocked_sample_count": len(blocked_samples),
        }
    routed = _best_routed_observations(annotated)
    return {
        "passed": bool(routed),
        "reason": "observe mode only records YOLO samples",
        "estimated_frames": estimated_frames,
        "observations": routed[:10],
    }


def _annotate_sample(sample: dict[str, Any], roi: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(sample)
    detections = []
    for det in out.get("detections") or []:
        if not isinstance(det, dict):
            continue
        item = copy.deepcopy(det)
        item["command"] = _command_for_detection(item)
        item["in_roi"] = bbox_in_roi(item.get("bbox"), roi)
        detections.append(item)
    out["detections"] = detections
    return out


def _command_for_detection(det: dict[str, Any]) -> str | None:
    command = str(det.get("uart_command") or "").strip().upper()
    return command if command in {"O", "R", "I"} else None


def _best_routed_observations(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for sample in samples:
        candidates = [
            det for det in sample.get("detections", []) if det.get("in_roi") and det.get("command")
        ]
        if candidates:
            observations.append(max(candidates, key=lambda det: float(det.get("confidence") or 0.0)))
    return observations


def _summarize_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "camera": config.get("camera"),
        "model": config.get("model"),
        "roi": config.get("roi"),
        "three_bin_classifier": config.get("three_bin_classifier"),
        "dispatch_guard": config.get("dispatch_guard"),
    }


def _expected_command(scenario: str, explicit: str) -> str | None:
    if explicit:
        return explicit
    return scenario if scenario in {"O", "R", "I"} else None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-url", default="http://127.0.0.1:8765")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--token", default="")
    parser.add_argument(
        "--scenario",
        choices=["camera_health", "empty", "O", "R", "I", "outside_roi", "multi_object", "observe"],
        default="camera_health",
    )
    parser.add_argument("--expected", choices=["O", "R", "I"], default="")
    parser.add_argument("--expected-class", default="")
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--min-observations", type=int, default=10)
    parser.add_argument("--min-correct", type=int, default=9)
    parser.add_argument("--max-seconds", type=float, default=30.0)
    parser.add_argument("--http-timeout", type=float, default=8.0)
    parser.add_argument("--camera-warmup-seconds", type=float, default=3.0)
    parser.add_argument("--start-camera", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out", type=Path, default=None)
    return parser


def _write_report(report: dict[str, Any], out: Path | None) -> Path:
    if out is None:
        slug = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = REPORT_DIR / f"yolo_camera_acceptance_{slug}_{report.get('scenario')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def _configure_console_utf8() -> None:
    with suppress(Exception):  # type: ignore[name-defined]
        sys.stdout.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
