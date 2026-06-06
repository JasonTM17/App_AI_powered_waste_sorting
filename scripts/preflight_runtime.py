"""Check local runtime readiness before plugging in USB camera/UART."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    _configure_console_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-url", default="http://127.0.0.1:8765")
    parser.add_argument("--web-url", default="http://127.0.0.1:3000")
    parser.add_argument("--model", type=Path, default=Path("models") / "best.pt")
    parser.add_argument("--fix-stale-locks", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    locks = _lock_summary(fix_stale=args.fix_stale_locks)

    report = {
        "agent": _get_json(f"{args.agent_url.rstrip('/')}/api/health"),
        "status": _get_json(f"{args.agent_url.rstrip('/')}/api/status"),
        "dataset": _get_json(f"{args.agent_url.rstrip('/')}/api/dataset/summary"),
        "web": _http_ok(args.web_url),
        "model_exists": args.model.exists(),
        "gpu": _gpu_summary(),
        "locks": locks,
    }
    ok = bool(
        report["agent"].get("ok")
        and report["web"].get("ok")
        and report["model_exists"]
        and report["dataset"].get("images", 0) >= 0
    )
    report["ok"] = ok
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Preflight: {'OK' if ok else 'NEEDS ATTENTION'}")
        print(f"Agent: {report['agent'].get('app', report['agent'].get('error', 'unknown'))}")
        print(f"Web: {report['web'].get('status', report['web'].get('error', 'unknown'))}")
        print(f"Model: {'found' if report['model_exists'] else 'missing'} ({args.model})")
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
        print(f"GPU: {report['gpu'].get('name', report['gpu'].get('error', 'unknown'))}")
    return 0 if ok else 1


def _get_json(url: str) -> dict[str, Any]:
    try:
        import httpx

        response = httpx.get(url, timeout=5)
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
