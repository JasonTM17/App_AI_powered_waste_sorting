"""Sidebar with mutually-exclusive nav buttons."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QPushButton, QVBoxLayout, QWidget


class Sidebar(QWidget):
    page_changed = Signal(int)

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(220)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(4)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []

        for idx, label in enumerate(items):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(btn, idx)
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()
        if self._buttons:
            self._buttons[0].setChecked(True)
        self._group.idClicked.connect(self.page_changed.emit)

    def set_active(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)
