from pathlib import Path

import app.utils.paths as paths_module
from app.utils.paths import (
    app_data_dir,
    detection_captures_dir,
    logs_dir,
    project_root,
    resolve_data_path,
    snapshots_dir,
)


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
    assert detection_captures_dir().name == "detection_captures"
    assert logs_dir().parent == app_data_dir()


def test_resolve_data_path_finds_project_data_from_frozen_dist(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    executable_dir = project_root / "dist" / "TrashSorterPro"
    dataset_dir = project_root / "dataset_v2"
    executable_dir.mkdir(parents=True)
    dataset_dir.mkdir()
    monkeypatch.chdir(executable_dir)
    monkeypatch.setattr(paths_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths_module.sys, "executable", str(executable_dir / "TrashSorterPro.exe"))
    monkeypatch.setattr(paths_module, "bundle_dir", lambda: executable_dir / "_internal")

    assert resolve_data_path("dataset_v2") == dataset_dir


def test_project_root_finds_source_root_from_frozen_dist(tmp_path, monkeypatch):
    source_root = tmp_path / "project"
    executable_dir = source_root / "dist" / "TrashSorterPro"
    executable_dir.mkdir(parents=True)
    monkeypatch.setattr(paths_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths_module.sys, "executable", str(executable_dir / "TrashSorterPro.exe"))

    assert project_root() == source_root
