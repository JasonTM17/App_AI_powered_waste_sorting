"""Check local runtime readiness before plugging in USB camera/UART."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
LOCAL_ENV_FILES = (".env", ".env.local")


def main() -> int:
    _configure_console_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-url", default="http://127.0.0.1:8765")
    parser.add_argument("--web-url", default="http://127.0.0.1:3000")
    parser.add_argument("--model", type=Path, default=Path("models") / "best.pt")
    parser.add_argument(
        "--token",
        default=_first_env(
            "TRASH_SORTER_PREFLIGHT_TOKEN",
            "TRASH_SORTER_ADMIN_TOKEN",
            "TRASH_SORTER_AGENT_TOKEN",
        ),
    )
    parser.add_argument("--username", default=_first_env("TRASH_SORTER_PREFLIGHT_USERNAME", "ADMIN_USERNAME"))
    parser.add_argument("--password", default=_first_env("TRASH_SORTER_PREFLIGHT_PASSWORD", "ADMIN_PASSWORD"))
    parser.add_argument(
        "--hardware-bridge-secret",
        default=_first_env("TRASH_SORTER_HARDWARE_BRIDGE_SECRET"),
    )
    parser.add_argument("--fix-stale-locks", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    locks = _lock_summary(fix_stale=args.fix_stale_locks)
    auth = _resolve_auth(
        args.agent_url,
        token=args.token,
        username=args.username,
        password=args.password,
        hardware_bridge_secret=args.hardware_bridge_secret,
    )
    headers = auth.get("headers", {})

    report = {
        "agent": _get_json(f"{args.agent_url.rstrip('/')}/api/health", headers=headers),
        "auth": auth.get("summary", {}),
        "status": _get_json(f"{args.agent_url.rstrip('/')}/api/status", headers=headers),
        "dataset": _get_json(f"{args.agent_url.rstrip('/')}/api/dataset/summary", headers=headers),
        "operations": _operations_summary(),
        "web": _http_ok(args.web_url),
        "model_exists": args.model.exists(),
        "hardware": {
            "real_hardware_required": False,
            "camera_required": False,
            "uart_required": False,
            "audio_required": False,
            "mode": "software_safety_only",
        },
        "gpu": _gpu_summary(),
        "locks": locks,
    }
    ok = bool(
        report["agent"].get("ok")
        and report["web"].get("ok")
        and report["model_exists"]
        and _payload_ok(report["status"])
        and _payload_ok(report["dataset"])
        and report["dataset"].get("images", 0) >= 0
        and report["operations"].get("ok", False)
    )
    report["ok"] = ok
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Preflight: {'OK' if ok else 'NEEDS ATTENTION'}")
        print(f"Agent: {report['agent'].get('app', report['agent'].get('error', 'unknown'))}")
        auth_summary = report.get("auth", {})
        auth_state = auth_summary.get("state", "none")
        auth_user = auth_summary.get("username", "")
        print(f"Auth: {auth_state}{f' user={auth_user}' if auth_user else ''}")
        print(f"Web: {report['web'].get('status', report['web'].get('error', 'unknown'))}")
        print(f"Model: {'found' if report['model_exists'] else 'missing'} ({args.model})")
        print("Hardware: software safety only; real camera/UART/audio are not required")
        status = report["status"]
        camera = status.get("camera", {})
        uart = status.get("uart", {})
        print(f"Camera: {camera.get('message', 'unknown')} source={status.get('current_source', '')!r}")
        print(f"UART: {uart.get('message', 'unknown')} port={status.get('current_port', '')!r}")
        for item in locks["items"]:
            state = "alive" if item.get("alive") else "stale" if item.get("stale") else "clear"
            removed = " removed" if item.get("removed") else ""
            print(f"Lock {item.get('name')}: {state}{removed} pid={item.get('pid')}")
        dataset = report["dataset"]
        print(
            "Dataset: "
            f"{dataset.get('images', 0)} images, "
            f"{dataset.get('boxes', 0)} boxes, "
            f"sync={not dataset.get('needs_sync', True)}"
        )
        operations = report["operations"]
        print(
            "Operations: "
            f"{operations.get('station_total', 0)} stations, "
            f"{operations.get('bin_total', 0)} bins, "
            f"seed={operations.get('seed_source', '')}"
        )
        print(f"GPU: {report['gpu'].get('name', report['gpu'].get('error', 'unknown'))}")
    return 0 if ok else 1


def _resolve_auth(
    agent_url: str,
    *,
    token: str,
    username: str,
    password: str,
    hardware_bridge_secret: str,
) -> dict[str, Any]:
    headers = _base_headers(hardware_bridge_secret)
    clean_token = token.strip()
    if clean_token:
        headers["Authorization"] = f"Bearer {clean_token}"
        return {"headers": headers, "summary": {"state": "token", "source": "argument_or_env"}}

    clean_username = username.strip()
    if not clean_username or not password:
        return {"headers": headers, "summary": {"state": "not_configured"}}

    try:
        import httpx

        response = httpx.post(
            f"{agent_url.rstrip('/')}/api/auth/login",
            json={"username": clean_username, "password": password},
            headers=headers,
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        session_token = str(data.get("token") or "").strip()
        if not session_token:
            return {
                "headers": headers,
                "summary": {
                    "state": "login_failed",
                    "username": clean_username,
                    "error": "missing token",
                },
            }
        headers["Authorization"] = f"Bearer {session_token}"
        return {
            "headers": headers,
            "summary": {
                "state": "session",
                "username": data.get("username", clean_username),
                "role": data.get("role", "unknown"),
                "password_default": bool(data.get("password_default")),
            },
        }
    except Exception as e:
        return {
            "headers": headers,
            "summary": {"state": "login_failed", "username": clean_username, "error": str(e)},
        }


def _base_headers(hardware_bridge_secret: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    clean_secret = hardware_bridge_secret.strip()
    if clean_secret:
        headers["X-Hardware-Bridge-Secret"] = clean_secret
    return headers


def _get_json(url: str, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        import httpx

        response = httpx.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {"value": data}
    except Exception as e:
        return {"error": str(e)}


def _http_ok(url: str) -> dict[str, Any]:
    try:
        import httpx

        response = httpx.get(url, timeout=5)
        return {"ok": response.status_code < 500, "status": response.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _payload_ok(payload: dict[str, Any]) -> bool:
    return "error" not in payload


def _first_env(*names: str) -> str:
    file_env = _local_env()
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
        value = file_env.get(name, "").strip()
        if value:
            return value
    return ""


def _local_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for name in LOCAL_ENV_FILES:
        values.update(_read_env_file(ROOT / name))
    return values


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    values: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def _gpu_summary() -> dict[str, str]:
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader",
            ],
            text=True,
            timeout=5,
        ).strip()
    except Exception as e:
        return {"error": str(e)}
    first = output.splitlines()[0] if output else ""
    if "," not in first:
        return {"name": first}
    name, memory = [part.strip() for part in first.split(",", 1)]
    return {"name": name, "memory": memory}


def _operations_summary() -> dict[str, Any]:
    try:
        from app.agent.operations_store import OperationsStore
        from app.utils.paths import operations_db_path

        store = OperationsStore(operations_db_path())
        try:
            return store.health()
        finally:
            store.close()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _lock_summary(*, fix_stale: bool) -> dict[str, Any]:
    try:
        from app.utils.runtime_lock import cleanup_stale_runtime_locks, inspect_runtime_lock

        cleaned = cleanup_stale_runtime_locks() if fix_stale else []
        items = [inspect_runtime_lock("camera"), inspect_runtime_lock("uart")]
        removed_by_name = {item["name"]: item for item in cleaned}
        for item in items:
            if item["name"] in removed_by_name:
                item["removed"] = True
        return {"items": items, "cleaned": cleaned}
    except Exception as e:
        return {"items": [], "cleaned": [], "error": str(e)}


def _configure_console_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
