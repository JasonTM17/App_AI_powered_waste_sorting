import sys

from app.utils.logging import (
    _has_console_stream,
    _resolve_log_dir,
    _resolve_log_file,
    setup_logging,
)


def test_resolve_log_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("app.utils.logging.logs_dir", lambda: tmp_path / "appdata" / "logs")
    d = _resolve_log_dir()
    assert d.name == "logs"
    assert d.parent.name == "appdata"
    assert d.exists()


def test_resolve_log_file_custom(tmp_path):
    custom = tmp_path / "custom.log"
    res = _resolve_log_file(custom)
    assert res == custom
    assert custom.parent.exists()


def test_resolve_log_file_default(tmp_path, monkeypatch):
    monkeypatch.setattr("app.utils.logging.logs_dir", lambda: tmp_path / "logs")
    res = _resolve_log_file()
    assert res.name.startswith("app-")
    assert res.name.endswith(".log")
    assert res.parent == tmp_path / "logs"


def test_has_console_stream(monkeypatch):
    assert _has_console_stream() is True
    monkeypatch.delattr(sys, "stderr", raising=False)
    assert _has_console_stream() is False


def test_setup_logging(tmp_path):
    log_file = tmp_path / "test.log"
    res = setup_logging(level="DEBUG", log_file=log_file)
    assert res == log_file
