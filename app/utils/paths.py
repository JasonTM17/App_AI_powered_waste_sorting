"""Cross-platform user data paths."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "TrashSorter"


def app_data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        path = Path(base) / APP_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        path = Path(base) / "trash-sorter"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    p = app_data_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def snapshots_dir() -> Path:
    p = app_data_dir() / "snapshots"
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_path() -> Path:
    return app_data_dir() / "config.json"


def db_path() -> Path:
    return app_data_dir() / "history.db"
