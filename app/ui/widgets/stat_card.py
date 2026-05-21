"""Compact stat card: label + value + sublabel."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class StatCard(QWidget):
    def __init__(self, label: str, value: str = "—", sub: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumHeight(96)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self._label = QLabel(label.upper())
        self._label.setStyleSheet(
            "color: #94A3B8; font-size: 11px; font-weight: 600; letter-spacing: 1px;"
        )
        layout.addWidget(self._label)

        self._value = QLabel(value)
        self._value.setStyleSheet(
            "font-size: 28px; font-weight: 700; color: #F1F5F9;"
            " font-family: 'JetBrains Mono','Consolas',monospace;"
        )
        layout.addWidget(self._value)

        self._sub = QLabel(sub)
        self._sub.setStyleSheet("color: #94A3B8; font-size: 11px;")
        layout.addWidget(self._sub)

        layout.addStretch()

    def set_value(self, value: str) -> None:
        self._value.setText(value)

    def set_sub(self, sub: str) -> None:
        self._sub.setText(sub)
