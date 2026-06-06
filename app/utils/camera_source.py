"""Helpers for normalizing user-facing camera source labels."""

from __future__ import annotations

import re

_INDEX_LABEL_RE = re.compile(r"^\s*(\d+)(?=\s*(?:$|\(|\[|:|-|\u2013|\u2014))")
_BACKEND_HINT_RE = re.compile(r"\((MSMF|DSHOW|ANY)\)", re.IGNORECASE)


def normalize_camera_source(value: object) -> str:
    """Return the OpenCV source from a raw value or a UI label."""
    raw = str(value or "").strip()
    match = _INDEX_LABEL_RE.match(raw)
    if match:
        return match.group(1)
    return raw


def opencv_camera_source(value: object) -> int | str:
    source = normalize_camera_source(value)
    return int(source) if source.isdigit() else source


def backend_hint(value: object) -> str | None:
    match = _BACKEND_HINT_RE.search(str(value or ""))
    return match.group(1).upper() if match else None


__all__ = ["backend_hint", "normalize_camera_source", "opencv_camera_source"]
