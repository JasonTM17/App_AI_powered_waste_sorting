import os

import pytest

from app.utils import runtime_lock as runtime_lock_module
from app.utils.runtime_lock import (
    RuntimeLock,
    RuntimeLockError,
    cleanup_stale_runtime_locks,
    inspect_runtime_lock,
)


def test_runtime_lock_removes_stale_pid(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(runtime_lock_module, "app_data_dir", lambda: tmp_path)
    lock_file = tmp_path / "camera.lock"
    lock_file.write_text("999999999", encoding="ascii")

    lock = RuntimeLock("camera")
    lock.acquire()

    assert lock_file.read_text(encoding="ascii") == str(os.getpid())
    lock.release()
    assert not lock_file.exists()


def test_runtime_lock_keeps_live_holder(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(runtime_lock_module, "app_data_dir", lambda: tmp_path)
    lock = RuntimeLock("camera")
    lock.acquire()

    try:
        with pytest.raises(RuntimeLockError):
            RuntimeLock("camera").acquire()
    finally:
        lock.release()


def test_cleanup_stale_runtime_locks_only_removes_dead_pid(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(runtime_lock_module, "app_data_dir", lambda: tmp_path)
    (tmp_path / "uart.lock").write_text("999999999", encoding="ascii")

    cleaned = cleanup_stale_runtime_locks(("uart",))

    assert cleaned
    assert not (tmp_path / "uart.lock").exists()
    assert inspect_runtime_lock("uart")["exists"] is False
