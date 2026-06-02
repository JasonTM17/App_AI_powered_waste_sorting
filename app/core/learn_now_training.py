"""Shared Learn Now candidate training process helpers."""

from __future__ import annotations

import csv
import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path


def start_learn_now_training(
    root: Path,
    class_name: str,
    profile: str,
    *,
    popen: Callable[..., object] | None = None,
) -> int:
    """Start a candidate-only Learn Now training script and return its PID."""
    script = root / "scripts" / (
        "start_vietnam_common_strong_train.ps1"
        if profile == "strong"
        else "start_learn_now_micro_train.ps1"
    )
    if not script.exists():
        raise FileNotFoundError(f"Missing training script: {script}")

    command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    if profile == "strong":
        command.extend(["-FocusClass", class_name])
    else:
        command.extend(["-ClassName", class_name, "-Profile", profile])

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    launcher = popen or subprocess.Popen
    process = launcher(
        command,
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    return int(process.pid)


def build_training_status(root: Path) -> dict[str, object]:
    """Return latest candidate training status without importing API schemas."""
    processes = training_processes()
    run_name = _active_training_run(processes)
    if not run_name:
        run_name = latest_training_run(root)

    if not run_name:
        return {
            "running": False,
            "run_name": "",
            "log_path": "",
            "results_path": "",
            "best_model_path": "",
            "last_model_path": "",
            "segment_epoch": None,
            "segment_epochs": None,
            "completed_epoch": None,
            "target_epoch": None,
            "progress_percent": 0.0,
            "precision": None,
            "recall": None,
            "map50": None,
            "map5095": None,
            "message": "Chưa có run huấn luyện nào.",
        }

    run_dir = root / "runs" / "train" / run_name
    args = read_simple_yaml(run_dir / "args.yaml")
    results_path = run_dir / "results.csv"
    latest = latest_csv_row(results_path)
    segment_epoch = _int_or_none(latest.get("epoch")) + 1 if latest else None
    segment_epochs = _int_or_none(args.get("epochs"))
    if segment_epoch is not None and segment_epochs is not None:
        segment_epoch = min(segment_epoch, segment_epochs)
    offset = _resume_epoch_offset(root, str(args.get("model") or ""))
    completed_epoch = offset + segment_epoch if segment_epoch is not None else None
    target_epoch = offset + segment_epochs if segment_epochs is not None else None
    if completed_epoch is not None and target_epoch is not None:
        completed_epoch = min(completed_epoch, target_epoch)
    progress = (
        min(100.0, round((completed_epoch / target_epoch) * 100, 1))
        if completed_epoch is not None and target_epoch
        else 0.0
    )
    log_path = latest_training_log(root, run_name)
    best_model = run_dir / "weights" / "best.pt"
    last_model = run_dir / "weights" / "last.pt"
    running = bool(processes)
    if completed_epoch is not None and target_epoch is not None:
        message = (
            f"Đang chạy {completed_epoch}/{target_epoch}"
            if running
            else f"Đã dừng ở {completed_epoch}/{target_epoch}"
        )
    else:
        message = "Đang huấn luyện" if running else "Training đang tắt"

    return {
        "running": running,
        "run_name": run_name,
        "log_path": str(log_path) if log_path else "",
        "results_path": str(results_path) if results_path.exists() else "",
        "best_model_path": str(best_model) if best_model.exists() else "",
        "last_model_path": str(last_model) if last_model.exists() else "",
        "segment_epoch": segment_epoch,
        "segment_epochs": segment_epochs,
        "completed_epoch": completed_epoch,
        "target_epoch": target_epoch,
        "progress_percent": progress,
        "precision": _float_or_none(latest.get("metrics/precision(B)") if latest else None),
        "recall": _float_or_none(latest.get("metrics/recall(B)") if latest else None),
        "map50": _float_or_none(latest.get("metrics/mAP50(B)") if latest else None),
        "map5095": _float_or_none(latest.get("metrics/mAP50-95(B)") if latest else None),
        "message": message,
    }


def training_processes() -> list[dict[str, object]]:
    if os.name != "nt":
        return []
    command = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { ($_.CommandLine -like '*scripts\\train_yolo.py*' "
        "-or $_.CommandLine -like '*scripts\\train_three_bin_classifier.py*' "
        "-or $_.CommandLine -like '*start_learn_now_micro_train.ps1*' "
        "-or $_.CommandLine -like '*start_vietnam_common_strong_train.ps1*') "
        "-and $_.CommandLine -notlike '*Where-Object*scripts\\train_yolo.py*' "
        "-and $_.CommandLine -notlike '*Where-Object*scripts\\train_three_bin_classifier.py*' "
        "-and $_.CommandLine -notlike '*Where-Object*start_learn_now_micro_train.ps1*' "
        "-and $_.CommandLine -notlike '*Where-Object*start_vietnam_common_strong_train.ps1*' } | "
        "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Depth 3"
    )
    try:
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command],
            capture_output=True,
            check=False,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    raw = res.stdout.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def stop_training_processes(pid: int | None = None) -> list[int]:
    """Stop known local training processes. Returns stopped process IDs."""
    if os.name != "nt":
        return []
    processes = training_processes()
    ids: list[int] = []
    for process in processes:
        value = process.get("ProcessId")
        try:
            process_id = int(str(value))
        except (TypeError, ValueError):
            continue
        if pid is not None and process_id != int(pid):
            continue
        ids.append(process_id)
    if not ids:
        return []
    id_list = ",".join(str(item) for item in ids)
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", f"Stop-Process -Id {id_list} -Force"],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return ids


def latest_training_run(root: Path) -> str:
    train_dir = root / "runs" / "train"
    if not train_dir.exists():
        return ""
    candidates = [path for path in train_dir.iterdir() if (path / "results.csv").exists()]
    if not candidates:
        return ""
    latest = max(candidates, key=lambda path: (path / "results.csv").stat().st_mtime)
    return latest.name


def latest_training_log(root: Path, run_name: str) -> Path | None:
    log_dir = root / "runs" / "train_logs"
    if not log_dir.exists():
        return None
    files = sorted(log_dir.glob(f"{run_name}-*.log"), key=lambda path: path.stat().st_mtime)
    return files[-1] if files else None


def latest_csv_row(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        return {}
    return dict(rows[-1]) if rows else {}


def read_simple_yaml(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip().strip("'\"")
    return out


def _active_training_run(processes: list[dict[str, object]]) -> str:
    for process in processes:
        command = str(process.get("CommandLine") or "")
        marker = "--name"
        parts = command.split()
        for index, part in enumerate(parts):
            if part == marker and index + 1 < len(parts):
                return parts[index + 1].strip("\"'")
    return ""


def _resume_epoch_offset(root: Path, model_path: str) -> int:
    normalized = model_path.replace("/", os.sep)
    markers = [f"{os.sep}runs{os.sep}train{os.sep}", f"runs{os.sep}train{os.sep}"]
    marker = next((item for item in markers if item in normalized), "")
    if not marker:
        return 0
    tail = normalized.split(marker, 1)[1]
    previous_run = tail.split(os.sep, 1)[0]
    latest = latest_csv_row(root / "runs" / "train" / previous_run / "results.csv")
    epoch = _int_or_none(latest.get("epoch"))
    return epoch + 1 if epoch is not None else 0


def _int_or_none(value: object) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _float_or_none(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


__all__ = [
    "build_training_status",
    "latest_csv_row",
    "latest_training_log",
    "latest_training_run",
    "read_simple_yaml",
    "start_learn_now_training",
    "stop_training_processes",
    "training_processes",
]
