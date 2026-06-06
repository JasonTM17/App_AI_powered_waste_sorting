"""Small file locks used to avoid two app runtimes opening the same hardware."""

from __future__ import annotations

import os
import time

from app.utils.paths import app_data_dir

LOCK_TTL_SECONDS = 24 * 60 * 60


class RuntimeLockError(RuntimeError):
    pass


class RuntimeLock:
    def __init__(self, name: str):
        self.name = name
        self.path = app_data_dir() / f"{name}.lock"
        self._acquired = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            age = time.time() - self.path.stat().st_mtime
            if age > LOCK_TTL_SECONDS or not self._holder_alive():
                self.path.unlink(missing_ok=True)
            else:
                raise RuntimeLockError(f"{self.name} đang được runtime khác sử dụng")
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        fd = os.open(str(self.path), flags)
        try:
            os.write(fd, str(os.getpid()).encode("ascii"))
        finally:
            os.close(fd)
        self._acquired = True

    def release(self) -> None:
        if not self._acquired:
            return
        self.path.unlink(missing_ok=True)
        self._acquired = False

    def _holder_alive(self) -> bool:
        try:
            pid = int(self.path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            return False
        if pid <= 0:
            return False
        if os.name == "nt":
            return _windows_process_alive(pid)
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True


def _windows_process_alive(pid: int) -> bool:
    try:
        import ctypes
    except ImportError:
        return False

    process_query_limited_information = 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    kernel32.CloseHandle(handle)
    return True


def acquire_runtime_lock(name: str) -> RuntimeLock:
    lock = RuntimeLock(name)
    lock.acquire()
    return lock


def inspect_runtime_lock(name: str) -> dict[str, object]:
    lock = RuntimeLock(name)
    exists = lock.path.exists()
    pid: int | None = None
    alive = False
    if exists:
        try:
            pid = int(lock.path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            pid = None
        alive = lock._holder_alive() if pid is not None else False
    return {
        "name": name,
        "path": str(lock.path),
        "exists": exists,
        "pid": pid,
        "alive": alive,
        "stale": exists and not alive,
    }


def cleanup_stale_runtime_locks(names: tuple[str, ...] = ("camera", "uart")) -> list[dict[str, object]]:
    cleaned: list[dict[str, object]] = []
    for name in names:
        lock = RuntimeLock(name)
        status = inspect_runtime_lock(name)
        if not status["stale"]:
            continue
        lock.path.unlink(missing_ok=True)
        status["removed"] = True
        cleaned.append(status)
    return cleaned


__all__ = [
    "RuntimeLock",
    "RuntimeLockError",
    "acquire_runtime_lock",
    "cleanup_stale_runtime_locks",
    "inspect_runtime_lock",
]
