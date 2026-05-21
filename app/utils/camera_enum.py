"""Detect USB cameras attached to the system.

Goal: distinguish a real USB camera the user just plugged in from the
laptop's built-in webcam, so the app refuses to fall back on the webcam
when the requested USB device isn't connected.

On Windows we read PnP entities via PowerShell — no extra dependency.
On other OSes the helpers degrade to a permissive 'unknown' verdict so
behaviour matches the previous app on the user's main target (Windows).
"""

from __future__ import annotations

import json
import os
import subprocess


def list_pnp_cameras() -> list[dict]:
    """Return [{name, instance_id, is_usb}] for every camera the OS sees."""
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
        result.append({"name": name, "instance_id": did, "is_usb": is_usb})
    return result


def has_external_camera() -> bool:
    """True if at least one USB camera is currently plugged in.

    Returns True (permissive) on non-Windows or when PnP enumeration is
    unavailable so the start path stays unblocked on those platforms.
    """
    if os.name != "nt":
        return True
    cams = list_pnp_cameras()
    if not cams:
        # could be a hardening config that blocks WMI; let the user try
        return True
    return any(c.get("is_usb") for c in cams)


__all__ = ["list_pnp_cameras", "has_external_camera"]
