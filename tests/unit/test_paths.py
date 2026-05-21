from pathlib import Path

from app.utils.paths import app_data_dir, logs_dir, snapshots_dir


def test_app_data_dir_returns_path(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = app_data_dir()
    assert isinstance(p, Path)
    assert p.exists()
    assert p.name == "TrashSorter"


def test_logs_and_snapshots_subdirs(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert logs_dir().name == "logs"
    assert snapshots_dir().name == "snapshots"
    assert logs_dir().parent == app_data_dir()
