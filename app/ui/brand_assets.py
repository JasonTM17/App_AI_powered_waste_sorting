"""Shared desktop brand asset resolution."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

from app.utils.paths import resource_path


def brand_mark_path() -> Path:
    return resource_path("app/ui/resources/icons/logo-512.png")


def app_icon_path() -> Path:
    return resource_path("app/ui/resources/icons/app.ico")


def brand_icon() -> QIcon:
    for path in (app_icon_path(), brand_mark_path()):
        if path.exists():
            return QIcon(str(path))
    return QIcon()
