"""Compatibility helpers for Ultralytics label scans on restricted Windows runtimes."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from types import TracebackType
from typing import Any


class SerialPool:
    """Small ThreadPool-compatible context that evaluates ``imap`` serially."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def __enter__(self) -> SerialPool:
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        return None

    def imap(self, func: Any, iterable: Iterable[Any]) -> Iterator[Any]:
        return map(func, iterable)


def enable_serial_label_cache() -> None:
    """Avoid Windows multiprocessing pipes while Ultralytics validates labels."""

    import ultralytics.data.dataset as dataset_module

    dataset_module.ThreadPool = SerialPool


__all__ = ["SerialPool", "enable_serial_label_cache"]
