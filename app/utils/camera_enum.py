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

_BUILTIN_NAME_HINTS = (
    "integrated",
    "built-in",
    "builtin",
    "internal",
    "hp truevision",
    "hp wide vision",
    "ealsia",
)


def _is_builtin(name: str) -> bool:
    n = name.lower()
    return any(h in n for h in _BUILTIN_NAME_HINTS)


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
    if os.name != "nt":
        return None
    external_names = {
        (c.get("name") or "").strip().lower()
        for c in list_pnp_cameras()
        if c.get("is_external")
    }
    if not external_names:
        return None
    dshow_names = list_directshow_cameras()
    if not dshow_names:
        return None
    try:
        import cv2
    except Exception:
        return None
    for idx, name in enumerate(dshow_names[: max_idx + 1]):
        if name.strip().lower() not in external_names:
            continue
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        try:
            ok = cap.isOpened()
            if ok:
                ok, frame = cap.read()
                ok = ok and frame is not None
            if ok:
                return f"{idx} (DSHOW)"
        finally:
            cap.release()
    return None


__all__ = [
    "find_readable_usb_camera",
    "has_external_camera",
    "list_directshow_cameras",
    "list_pnp_cameras",
]
