"""Qt thread wrapper for starting the local web dashboard."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app.utils.local_web import ensure_local_web_stack


class WebLauncherThread(QThread):
    done = Signal(bool, str, str)

    def run(self) -> None:
        result = ensure_local_web_stack()
        self.done.emit(result.ok, result.message, result.url)
