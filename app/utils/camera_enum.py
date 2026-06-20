"""Detect USB cameras attached to the system.

Goal: distinguish a real USB camera the user just plugged in from the
laptop's built-in webcam, so the app refuses to fall back on the webcam
when the requested USB device isn't connected.

On Windows we read PnP entities via PowerShell - no extra dependency.
On other OSes the helpers degrade to a permissive 'unknown' verdict so
behaviour matches the previous app on the user's main target (Windows).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time

from app.utils.camera_frame_quality import best_frame_quality, evaluate_frame_quality

_BUILTIN_NAME_HINTS = (
    "integrated",
    "built-in",
    "builtin",
    "internal",
    "hp truevision",
    "hp wide vision",
    "ealsia",
)
_VIRTUAL_CAMERA_HINTS = (
    "obs virtual",
    "virtual camera",
    "snap camera",
    "xsplit",
    "manycam",
)


def _is_builtin(name: str) -> bool:
    n = name.lower()
    return any(h in n for h in _BUILTIN_NAME_HINTS)


def _is_virtual_camera(name: str) -> bool:
    n = name.lower()
    return any(h in n for h in _VIRTUAL_CAMERA_HINTS)


def _is_external_directshow_name(name: str) -> bool:
    return bool(name.strip()) and not _is_builtin(name) and not _is_virtual_camera(name)


def list_pnp_cameras() -> list[dict]:
    """Return [{name, instance_id, is_usb, is_external}] for every camera."""
    if os.name != "nt":
        return []
    ps = (
        "Get-CimInstance -ClassName Win32_PnPEntity "
        "-Filter \"PNPClass='Camera' OR PNPClass='Image'\" "
        "| Select-Object Name, DeviceID "
        "| ConvertTo-Json -Compress"
    )
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            timeout=5,
            text=True,
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return []
    out = out.strip()
    if not out:
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = (item.get("Name") or "").strip()
        did = (item.get("DeviceID") or "").strip()
        is_usb = "USB" in did.upper()
        is_external = is_usb and not _is_builtin(name)
        result.append(
            {
                "name": name,
                "instance_id": did,
                "is_usb": is_usb,
                "is_external": is_external,
            }
        )
    return result


def has_external_camera() -> bool:
    """True if at least one external (non-laptop-built-in) USB camera is plugged in."""
    if os.name != "nt":
        return True
    cams = list_pnp_cameras()
    if not cams:
        return True
    return any(c.get("is_external") for c in cams)


def list_directshow_cameras() -> list[str]:
    """Return DirectShow camera names if ffmpeg is available on PATH."""
    if os.name != "nt" or not shutil.which("ffmpeg"):
        return []
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            timeout=5,
            capture_output=True,
            text=True,
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except Exception:
        return []
    text = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
    names: list[str] = []
    for line in text.splitlines():
        if "(video)" not in line:
            continue
        match = re.search(r'"([^"]+)"\s+\(video\)', line)
        if match:
            names.append(match.group(1).strip())
    return names


def find_readable_usb_camera(max_idx: int = 9) -> str | None:
    """Return an OpenCV source label for the first readable external USB camera."""
    probes = probe_usb_cameras(max_idx=max_idx)
    for item in probes:
        if item.get("usable"):
            return str(item.get("source") or "")
    return None


def probe_usb_cameras(max_idx: int = 9) -> list[dict[str, object]]:
    """Probe external USB camera indexes and reject black frames."""
    if os.name != "nt":
        return []
    external_names = {
        (c.get("name") or "").strip().lower()
        for c in list_pnp_cameras()
        if c.get("is_external")
    }
    dshow_names = list_directshow_cameras()
    if not dshow_names:
        return []
    try:
        import cv2
    except Exception:
        return []
    probes: list[dict[str, object]] = []
    for idx, name in enumerate(dshow_names[: max_idx + 1]):
        normalized_name = name.strip().lower()
        if external_names:
            should_probe = normalized_name in external_names
        else:
            should_probe = _is_external_directshow_name(name)
        if not should_probe:
            continue
        for backend_name, backend in (
            ("DSHOW", cv2.CAP_DSHOW),
            ("MSMF", cv2.CAP_MSMF),
            ("ANY", cv2.CAP_ANY),
        ):
            source = f"{idx} ({backend_name})"
            cap = cv2.VideoCapture(idx, backend)
            try:
                opened = bool(cap.isOpened())
                quality = _sample_capture_quality(cap) if opened else None
                probes.append(
                    {
                        "source": source,
                        "index": idx,
                        "backend": backend_name,
                        "name": name,
                        "opened": opened,
                        "usable": bool(quality and quality.usable),
                        "quality": quality.to_dict() if quality is not None else None,
                        "reason": quality.reason if quality is not None else "cannot open source",
                    }
                )
                if quality is not None and quality.usable:
                    return probes
            finally:
                cap.release()
    return probes


def camera_unavailable_message() -> str:
    """Human-readable USB camera diagnostic for the desktop UI."""
    dshow_names = list_directshow_cameras()
    if not dshow_names:
        return (
            "Chưa thấy camera USB đọc được frame. Windows/DirectShow chưa liệt kê camera nào; "
            "hãy cắm lại USB camera, đóng app khác đang dùng camera, rồi bật lại."
        )
    visible = ", ".join(dshow_names[:4])
    suffix = "" if len(dshow_names) <= 4 else ", ..."
    if not any(_is_external_directshow_name(name) for name in dshow_names):
        return (
            "Chưa thấy camera USB thật đọc được frame. DirectShow hiện chỉ thấy: "
            f"{visible}{suffix}. Hãy cắm lại USB camera thật hoặc kiểm tra quyền camera."
        )
    return (
        "Camera USB có xuất hiện nhưng chưa đọc được frame usable. DirectShow thấy: "
        f"{visible}{suffix}. Hãy kiểm tra dây USB, app đang chiếm camera, ánh sáng và focus."
    )


def _sample_capture_quality(cap, *, frames: int = 5):
    qualities = []
    for _ in range(max(1, frames)):
        ok, frame = cap.read()
        if ok and frame is not None:
            qualities.append(evaluate_frame_quality(frame))
        time.sleep(0.03)
    return best_frame_quality(qualities)


__all__ = [
    "camera_unavailable_message",
    "find_readable_usb_camera",
    "has_external_camera",
    "_is_external_directshow_name",
    "list_directshow_cameras",
    "list_pnp_cameras",
    "probe_usb_cameras",
]
