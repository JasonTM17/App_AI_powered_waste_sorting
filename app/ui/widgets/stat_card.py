"""Compact stat card: label + value + sublabel."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class StatCard(QFrame):
    def __init__(self, label: str, value: str = "—", sub: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumHeight(108)
        self.setMinimumWidth(120)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(5)

        self._label = QLabel(label.upper())
        self._label.setStyleSheet(
            "color: #BBCABF; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
            " font-family: 'Consolas';"
        )
        layout.addWidget(self._label)

        self._value = QLabel(value)
        self._value.setStyleSheet(
            "font-size: 28px; font-weight: 800; color: #6FFBBE;"
            " font-family: 'Consolas';"
        )
        layout.addWidget(self._value)

        self._sub = QLabel(sub)
        self._sub.setStyleSheet("color: #BBCABF; font-size: 12px;")
        layout.addWidget(self._sub)

        layout.addStretch()

    def set_value(self, value: str) -> None:
        self._value.setText(value)

    def set_sub(self, sub: str) -> None:
        self._sub.setText(sub)
