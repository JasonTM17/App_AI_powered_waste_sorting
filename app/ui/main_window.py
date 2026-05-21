"""Frameless main window: title bar + sidebar + stacked pages + status bar."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets.sidebar import Sidebar
from app.ui.widgets.title_bar import TitleBar

NAV_ITEMS = ["▶  Live", "▦  Lịch sử", "⇆  Mapping", "◉  Capture", "⚙  Cài đặt"]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.resize(1280, 800)

        root = QWidget()
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = TitleBar("Trash Sorter Pro")
        self.title_bar.minimize_requested.connect(self.showMinimized)
        self.title_bar.maximize_toggled.connect(self._toggle_max)
        self.title_bar.close_requested.connect(self.close)
        outer.addWidget(self.title_bar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = Sidebar(NAV_ITEMS)
        self.stack = QStackedWidget()
        for label in NAV_ITEMS:
            page = QLabel(f"{label} — placeholder")
            page.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stack.addWidget(page)
        self.sidebar.page_changed.connect(self.stack.setCurrentIndex)

        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(self.stack, 1)
        outer.addWidget(body, 1)

        self.status = QLabel("● Camera —  •  ● UART —  •  ● Model —  •  FPS 0  ")
        self.status.setObjectName("statusbar")
        self.status.setFixedHeight(32)
        self.status.setContentsMargins(16, 0, 16, 0)
        outer.addWidget(self.status)

        for i in range(5):
            QShortcut(
                QKeySequence(f"Ctrl+{i+1}"),
                self,
                activated=lambda i=i: (
                    self.sidebar.set_active(i),
                    self.stack.setCurrentIndex(i),
                ),
            )
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.close)

    def _toggle_max(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
