"""Run Phase 23 no-UART camera acceptance for the 3-bin fallback."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

import httpx

websocket_connect: Any = None
try:
    from websockets.sync.client import connect as websocket_connect
except Exception:  # pragma: no cover - environment dependent
    websocket_connect = None

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.three_bin_classifier import parse_three_bin_class_name  # noqa: E402

REPORT_DIR = ROOT / "runs" / "eval"
THREE_BIN_DEFAULT = {
    "enabled": True,
    "model_path": "models/three_bin_classifier.pt",
    "min_confidence": 0.72,
    "min_margin": 0.12,
    "unknown_only": True,
    "min_crop_area_ratio": 0.003,
    "input_size": 224,
}
MAX_ESTIMATED_FPS = 30.0
def main() -> int:
    _configure_console_utf8()
    parser = _parser()
    args = parser.parse_args()
    report = run_acceptance(args)
    path = _write_report(report, args.out)
    analysis = report.get("analysis", {})
    print(f"Phase 23 report: {path}")
    print(f"Scenario: {report.get('scenario')} pass={analysis.get('passed')}")
    print(f"Reason: {analysis.get('reason', '')}")
    return 0 if analysis.get("passed") else 2


def run_acceptance(args: argparse.Namespace) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    original_config: dict[str, Any] | None = None
    report: dict[str, Any] = {
        "phase": 23,
        "generated_at": generated_at,
        "scenario": args.scenario,
        "expected_command": _expected_command(args.scenario, args.expected),
        "target_frames": args.frames,
        "min_observations": args.min_observations,
        "min_correct": args.min_correct,
        "safety": {
            "uart_test_mode_requested": False,
            "hardware_dispatch_expected": False,
            "models_best_unchanged_check": str(ROOT / "models" / "best.pt"),
            "three_bin_model": str(ROOT / "models" / "three_bin_classifier.pt"),
        },
        "samples": [],
        "events": [],
    }

    with httpx.Client(timeout=args.http_timeout) as client:
        token = _resolve_token(client, args)
        headers = {"Authorization": f"Bearer {token}"}
        status_before = _get_json(client, args.agent_url, "/api/status?include_devices=true", headers)
        report["status_before"] = status_before

        actuation_before = _get_json(client, args.agent_url, "/api/actuation/test-mode", headers)
        report["actuation_before"] = _redact_evidence(actuation_before)
        _put_json(client, args.agent_url, "/api/actuation/test-mode", headers, {"enabled": False})
        report["actuation_forced_off"] = True

        settings = _get_json(client, args.agent_url, "/api/settings", headers)
        original_config = copy.deepcopy(settings.get("config") or {})
        test_config = _config_with_three_bin_enabled(original_config)
        _put_json(client, args.agent_url, "/api/settings", headers, test_config)
        report["test_config"] = _summarize_config(test_config)

        if args.start_camera:
            start_res = _post_json(client, args.agent_url, "/api/camera/start", headers, {})
            report["camera_start"] = start_res
            time.sleep(args.camera_warmup_seconds)

        status_after_setup = _get_json(
            client,
            args.agent_url,
            "/api/status?include_devices=true",
            headers,
        )
        report["status_after_setup"] = status_after_setup
        if not status_after_setup.get("camera", {}).get("running"):
            report["analysis"] = {
                "passed": False,
                "reason": "camera is not running; cannot execute real-camera acceptance",
            }
            report["actuation_after"] = _redact_evidence(
                _get_json(client, args.agent_url, "/api/actuation/test-mode", headers)
            )
            if original_config is not None and not args.leave_classifier_enabled:
                _put_json(client, args.agent_url, "/api/settings", headers, original_config)
                report["config_restored"] = True
            return report

        samples = _collect_live_samples(
            args.agent_url,
            token,
            target_frames=args.frames,
            max_seconds=args.max_seconds,
        )
        report["samples"] = samples
        roi = (test_config.get("roi") or {}) if isinstance(test_config, dict) else {}
        report["analysis"] = analyze_acceptance(
            samples,
            scenario=args.scenario,
            expected_command=report["expected_command"],
            roi=roi,
            target_frames=args.frames,
            min_observations=args.min_observations,
            min_correct=args.min_correct,
        )
        report["actuation_after"] = _redact_evidence(
            _get_json(client, args.agent_url, "/api/actuation/test-mode", headers)
        )
        if original_config is not None and not args.leave_classifier_enabled:
            _put_json(client, args.agent_url, "/api/settings", headers, original_config)
            report["config_restored"] = True
        else:
            report["config_restored"] = False
    return report


def analyze_acceptance(
    samples: list[dict[str, Any]],
    *,
    scenario: str,
    expected_command: str | None,
    roi: dict[str, Any],
    target_frames: int,
    min_observations: int,
    min_correct: int,
) -> dict[str, Any]:
    annotated = [_annotate_sample(sample, roi) for sample in samples]
    estimated_frames = max((int(sample.get("estimated_frames") or 0) for sample in annotated), default=0)
    camera_running = any(bool(sample.get("status", {}).get("camera", {}).get("running")) for sample in annotated)
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
                "empty tray had no in-ROI dispatch intent"
                if passed
                else "empty tray still needs 100 camera frames with no in-ROI route"
            ),
            "estimated_frames": estimated_frames,
            "false_dispatch_intents": routed_in_roi[:10],
        }

    if scenario in {"O", "R", "I"}:
        observations = _best_routed_observations(annotated)
        correct = [det for det in observations if det.get("command") == expected_command]
        passed = len(observations) >= min_observations and len(correct) >= min_correct
        return {
            "passed": passed,
            "reason": (
                f"{expected_command} camera route passed"
                if passed
                else f"need at least {min_correct}/{min_observations} correct {expected_command} routes"
            ),
            "observations": len(observations),
            "correct": len(correct),
            "commands": _count_values(det.get("command") for det in observations),
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
        passed = len(outside_routed) >= min_observations and not unsafe_inside
        return {
            "passed": passed,
            "reason": (
                "outside-ROI detections did not create in-ROI route"
                if passed
                else "need outside-ROI samples with no in-ROI route"
            ),
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
        passed = bool(multi_samples) and bool(blocked_samples)
        return {
            "passed": passed,
            "reason": (
                "multi-object scene warned and blocked"
                if passed
                else "need a multi-object in-ROI sample with 'multiple waste types' status"
            ),
            "multi_samples": multi_samples[:10],
            "blocked_sample_count": len(blocked_samples),
        }

    routed = _best_routed_observations(annotated)
    return {
        "passed": bool(routed),
        "reason": "observe mode only records samples",
        "estimated_frames": estimated_frames,
        "observations": routed[:10],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-url", default="http://127.0.0.1:8766")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--token", default="")
    parser.add_argument(
        "--scenario",
        choices=["empty", "O", "R", "I", "outside_roi", "multi_object", "observe"],
        default="empty",
    )
    parser.add_argument("--expected", choices=["O", "R", "I"], default="")
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--min-observations", type=int, default=10)
    parser.add_argument("--min-correct", type=int, default=9)
    parser.add_argument("--max-seconds", type=float, default=30.0)
    parser.add_argument("--http-timeout", type=float, default=8.0)
    parser.add_argument("--camera-warmup-seconds", type=float, default=3.0)
    parser.add_argument("--start-camera", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--leave-classifier-enabled", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    return parser


def _resolve_token(client: httpx.Client, args: argparse.Namespace) -> str:
    if args.token:
        return args.token
    res = client.post(
        f"{args.agent_url.rstrip('/')}/api/auth/login",
        json={"username": args.username, "password": args.password},
    )
    res.raise_for_status()
    token = str(res.json().get("token") or "")
    if not token:
        raise RuntimeError("login did not return a token")
    return token


def _collect_live_samples(
    agent_url: str,
    token: str,
    *,
    target_frames: int,
    max_seconds: float,
) -> list[dict[str, Any]]:
    if websocket_connect is None:
        return [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "estimated_frames": 0,
                "status": {},
                "detections": [],
                "error": "websockets.sync.client is not available",
            }
        ]
    ws_url = _ws_live_url(agent_url, token)
    deadline = time.monotonic() + max_seconds
    samples: list[dict[str, Any]] = []
    estimated_frames = 0
    last_seen = time.monotonic()
    with websocket_connect(ws_url, open_timeout=8) as ws:
        while time.monotonic() < deadline and estimated_frames < target_frames:
            raw = ws.recv(timeout=min(5.0, max(0.5, deadline - time.monotonic())))
            payload = json.loads(raw)
            now = time.monotonic()
            status = payload.get("status") or {}
            fps = float(status.get("fps") or 0.0)
            elapsed = max(0.0, now - last_seen)
            last_seen = now
            estimated_frames += _estimated_frame_increment(fps, elapsed)
            samples.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "estimated_frames": estimated_frames,
                    "status": status,
                    "detections": payload.get("detections") or [],
                }
            )
    return samples


def _estimated_frame_increment(fps: float, elapsed: float) -> int:
    if fps <= 0:
        return 1
    effective_fps = min(float(fps), MAX_ESTIMATED_FPS)
    return max(1, round(effective_fps * max(0.0, elapsed)))


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


def bbox_in_roi(bbox: object, roi: dict[str, Any]) -> bool:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return False
    if not bool(roi.get("enabled")) or int(roi.get("width") or 0) <= 0 or int(roi.get("height") or 0) <= 0:
        return True
    x1, y1, x2, y2 = [int(float(value)) for value in bbox]
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    rx = int(roi.get("x") or 0)
    ry = int(roi.get("y") or 0)
    rw = int(roi.get("width") or 0)
    rh = int(roi.get("height") or 0)
    return rx <= cx <= rx + rw and ry <= cy <= ry + rh


def _command_for_detection(det: dict[str, Any]) -> str | None:
    command = str(det.get("uart_command") or "").strip().upper()
    if command in {"O", "R", "I"}:
        return command
    parsed = parse_three_bin_class_name(str(det.get("cls_name") or ""))
    return parsed if parsed in {"O", "R", "I"} else None


def _best_routed_observations(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for sample in samples:
        candidates = [
            det
            for det in sample.get("detections", [])
            if det.get("in_roi") and det.get("command")
        ]
        if not candidates:
            continue
        observations.append(
            max(candidates, key=lambda det: float(det.get("confidence") or 0.0))
        )
    return observations


def _config_with_three_bin_enabled(config: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(config)
    current = out.get("three_bin_classifier")
    if not isinstance(current, dict):
        current = {}
    updated = dict(THREE_BIN_DEFAULT)
    updated.update(current)
    updated["enabled"] = True
    out["three_bin_classifier"] = updated
    return out


def _summarize_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "camera": config.get("camera"),
        "roi": config.get("roi"),
        "three_bin_classifier": config.get("three_bin_classifier"),
        "dispatch_guard": config.get("dispatch_guard"),
        "uart": {
            "port": (config.get("uart") or {}).get("port"),
            "protocol": (config.get("uart") or {}).get("protocol"),
        },
    }


def _expected_command(scenario: str, explicit: str) -> str | None:
    if explicit:
        return explicit
    return scenario if scenario in {"O", "R", "I"} else None


def _count_values(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _get_json(
    client: httpx.Client,
    agent_url: str,
    path: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    res = client.get(f"{agent_url.rstrip('/')}{path}", headers=headers)
    res.raise_for_status()
    data = res.json()
    return cast(dict[str, Any], data) if isinstance(data, dict) else {"value": data}


def _put_json(
    client: httpx.Client,
    agent_url: str,
    path: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    res = client.put(f"{agent_url.rstrip('/')}{path}", headers=headers, json=payload)
    res.raise_for_status()
    data = res.json()
    return cast(dict[str, Any], data) if isinstance(data, dict) else {"value": data}


def _post_json(
    client: httpx.Client,
    agent_url: str,
    path: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    res = client.post(f"{agent_url.rstrip('/')}{path}", headers=headers, json=payload)
    res.raise_for_status()
    data = res.json()
    return cast(dict[str, Any], data) if isinstance(data, dict) else {"value": data}


def _redact_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    for item in out.get("evidence") or []:
        if isinstance(item, dict):
            item.pop("serial_payload", None)
    return out


def _write_report(report: dict[str, Any], out: Path | None) -> Path:
    if out is None:
        slug = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = REPORT_DIR / f"three_bin_camera_acceptance_{slug}_{report.get('scenario')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def _ws_live_url(agent_url: str, token: str) -> str:
    base = agent_url.rstrip("/")
    if base.startswith("https://"):
        base = "wss://" + base[len("https://") :]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://") :]
    return f"{base}/ws/live?token={quote(token)}"


def _configure_console_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
