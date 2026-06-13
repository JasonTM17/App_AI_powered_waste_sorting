"""Cross-platform user data paths."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "TrashSorter"


def bundle_dir() -> Path:
    """Directory containing read-only resources bundled with the app.

    - When running from a PyInstaller frozen build, returns ``sys._MEIPASS``
      (one-folder mode: ``dist/TrashSorterPro/_internal/``).
    - When running from source, returns the project root (parent of ``app/``).
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent.parent


def resource_path(rel: str | Path) -> Path:
    """Resolve a relative resource path against the bundle dir.

    Absolute paths are returned unchanged.
    """
    p = Path(rel)
    if p.is_absolute():
        return p
    return bundle_dir() / p


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


def detection_captures_dir() -> Path:
    p = app_data_dir() / "detection_captures"
    p.mkdir(parents=True, exist_ok=True)
    return p


def recognition_test_captures_dir() -> Path:
    p = app_data_dir() / "recognition_tests"
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_path() -> Path:
    return app_data_dir() / "config.json"


def db_path() -> Path:
    return app_data_dir() / "history.db"


def dataset_db_path() -> Path:
    return app_data_dir() / "dataset.db"


def auth_db_path() -> Path:
    return app_data_dir() / "auth.db"


def operations_db_path() -> Path:
    return app_data_dir() / "operations.db"


def example_config_path() -> Path:
    """Path to the seed config bundled with the app."""
    return resource_path("config.example.json")
