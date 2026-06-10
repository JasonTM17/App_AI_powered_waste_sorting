"""System log viewer tab: tail JSONL log file with filter and search."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.utils.paths import logs_dir

_LEVEL_COLORS = {
    "DEBUG": "#86948A",
    "INFO": "#BBCABF",
    "SUCCESS": "#4EDEA3",
    "WARNING": "#F59E0B",
    "ERROR": "#F43F5E",
    "CRITICAL": "#FFB4AB",
}

_LEVEL_ORDER = ["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]


def _todays_log_path() -> Path:
    return logs_dir() / f"app-{datetime.now():%Y-%m-%d}.log"


class SystemLogPage(QWidget):
    log_cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._path: Path = _todays_log_path()
        self._offset = 0
        self._filter_level = "ALL"
        self._search = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(16)

        title = QLabel("Nhật ký hệ thống")
        title.setObjectName("h1")
        outer.addWidget(title)

        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(16, 12, 16, 12)
        tb.setSpacing(12)

        tb.addWidget(QLabel("Mức"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(["ALL", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR"])
        self.level_combo.currentTextChanged.connect(self._on_filter_changed)
        tb.addWidget(self.level_combo)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Tìm kiếm trong message…")
        self.search_edit.textChanged.connect(self._on_search_changed)
        tb.addWidget(self.search_edit, 1)

        self.btn_pause = QPushButton("⏸  Tạm dừng")
        self.btn_pause.setObjectName("secondary")
        self.btn_pause.setCheckable(True)
        self.btn_pause.toggled.connect(self._on_pause_toggled)
        tb.addWidget(self.btn_pause)

        btn_clear = QPushButton("⌫  Xoá hiển thị")
        btn_clear.setObjectName("secondary")
        btn_clear.clicked.connect(self._clear_view)
        tb.addWidget(btn_clear)

        btn_open = QPushButton("📂  Mở thư mục log")
        btn_open.setObjectName("secondary")
        btn_open.clicked.connect(self._open_logs_dir)
        tb.addWidget(btn_open)

        outer.addWidget(toolbar)

        self.path_label = QLabel(f"📄 {self._path}")
        self.path_label.setStyleSheet("color: #BBCABF; font-family: 'Consolas';")
        outer.addWidget(self.path_label)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setObjectName("card")
        self.view.setStyleSheet(
            "QPlainTextEdit { background: #060E20; border-radius: 10px; padding: 14px;"
            " font-family: 'Consolas'; font-size: 12px;"
            " border: 1px solid rgba(78,222,163,0.14); }"
        )
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        outer.addWidget(self.view, 1)

        footer = QHBoxLayout()
        self.count_label = QLabel("0 dòng")
        self.count_label.setObjectName("mono")
        footer.addWidget(self.count_label)
        footer.addStretch()
        outer.addLayout(footer)

        self._timer = QTimer(self)
        self._timer.setInterval(800)
        self._timer.timeout.connect(self._poll_log)
        self._timer.start()

        self._poll_log()

    def _on_filter_changed(self, level: str) -> None:
        self._filter_level = level
        self._reload_full()

    def _on_search_changed(self, text: str) -> None:
        self._search = text.strip().lower()
        self._reload_full()

    def _on_pause_toggled(self, paused: bool) -> None:
        if paused:
            self._timer.stop()
            self.btn_pause.setText("▶  Tiếp tục")
        else:
            self._timer.start()
            self.btn_pause.setText("⏸  Tạm dừng")

    def _clear_view(self) -> None:
        self.view.clear()
        self.log_cleared.emit()

    def _open_logs_dir(self) -> None:
        import os
        import subprocess

        d = str(logs_dir())
        try:
            if os.name == "nt":
                os.startfile(d)
            else:
                subprocess.Popen(["xdg-open", d])
        except Exception:
            pass

    def _format_line(self, raw: str) -> tuple[str, str] | None:
        try:
            obj = json.loads(raw)
            rec = obj.get("record", {})
            ts = rec.get("time", {}).get("repr", "")[:19].replace("T", " ")
            level = rec.get("level", {}).get("name", "INFO")
            msg = rec.get("message", "")
            module = rec.get("module", "")
            line = rec.get("line", "")
        except Exception:
            return ("INFO", raw.rstrip())

        if self._filter_level != "ALL" and level != self._filter_level:
            return None
        if self._search and self._search not in msg.lower():
            return None
        formatted = f"{ts}  {level:<8} {module}:{line}  {msg}"
        return (level, formatted)

    def _append_lines(self, lines: list[str]) -> None:
        scrollbar = self.view.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
        cursor = self.view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        appended = 0
        for raw in lines:
            r = self._format_line(raw)
            if r is None:
                continue
            level, text = r
            fmt = QTextCharFormat()
            color = _LEVEL_COLORS.get(level, "#F1F5F9")
            fmt.setForeground(QColor(color))
            cursor.setCharFormat(fmt)
            cursor.insertText(text + "\n")
            appended += 1
        if at_bottom:
            scrollbar.setValue(scrollbar.maximum())
        self._update_count()
        if appended == 0 and not lines:
            return

    def _update_count(self) -> None:
        n = max(0, self.view.blockCount() - 1)
        self.count_label.setText(f"{n} dòng")

    def _poll_log(self) -> None:
        path = _todays_log_path()
        if path != self._path:
            self._path = path
            self._offset = 0
            self.view.clear()
            self.path_label.setText(f"📄 {self._path}")
        if not path.exists():
            return
        try:
            size = path.stat().st_size
        except OSError:
            return
        if size < self._offset:
            self._offset = 0
            self.view.clear()
        if size == self._offset:
            return
        try:
            with path.open("rb") as f:
                f.seek(self._offset)
                chunk = f.read(size - self._offset)
            self._offset = size
        except OSError:
            return
        try:
            text = chunk.decode("utf-8", errors="replace")
        except Exception:
            return
        lines = [ln for ln in text.split("\n") if ln.strip()]
        if lines:
            self._append_lines(lines)

    def _reload_full(self) -> None:
        self.view.clear()
        self._offset = 0
        self._poll_log()
