"""Custom frameless window title bar."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class TitleBar(QWidget):
    minimize_requested = Signal()
    maximize_toggled = Signal()
    close_requested = Signal()

    def __init__(self, title: str = "Trash Sorter Pro", parent=None):
        super().__init__(parent)
        self.setObjectName("titlebar")
        self.setFixedHeight(40)
        self._drag_offset: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 0, 0)
        layout.setSpacing(0)

        self.label = QLabel(f"●  {title}")
        self.label.setStyleSheet("color: #F1F5F9; font-weight: 600;")
        layout.addWidget(self.label)
        layout.addStretch()

        self.btn_min = QPushButton("—")
        self.btn_max = QPushButton("□")
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("close-btn")

        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setFixedSize(46, 40)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(b)

        self.btn_min.clicked.connect(self.minimize_requested)
        self.btn_max.clicked.connect(self.maximize_toggled)
        self.btn_close.clicked.connect(self.close_requested)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self.window() is not None:
            self._drag_offset = e.globalPosition().toPoint() - self.window().pos()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag_offset is None or not (e.buttons() & Qt.MouseButton.LeftButton):
            return
        win = self.window()
        if win is None:
            return
        if win.isMaximized():
            # restore + re-anchor cursor near the original click x ratio
            global_pos = e.globalPosition().toPoint()
            ratio_x = max(0.0, min(1.0, e.position().x() / max(self.width(), 1)))
            win.showNormal()
            new_w = win.width()
            self._drag_offset = QPoint(int(new_w * ratio_x), e.position().toPoint().y())
            win.move(global_pos - self._drag_offset)
            return
        win.move(e.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        self._drag_offset = None

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
        self.maximize_toggled.emit()
