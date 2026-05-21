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

from app.core.config import AppConfig
from app.ui.widgets.sidebar import Sidebar
from app.ui.widgets.title_bar import TitleBar

NAV_ITEMS = ["▶  Live", "▦  Lịch sử", "⇆  Mapping", "◉  Capture", "⚙  Cài đặt"]


class MainWindow(QMainWindow):
    def __init__(self, cfg: AppConfig | None = None, history=None) -> None:
        super().__init__()
        self._force_quit = False
        self._minimize_to_tray = False
        self.tray = None
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
        from app.ui.pages.live import LivePage

        self.stack = QStackedWidget()
        self.live_page = LivePage()
        self.mapping_page = None
        self.history_page = None
        self.capture_page = None
        self.stack.addWidget(self.live_page)
        for idx, label in enumerate(NAV_ITEMS[1:4], start=1):
            if idx == 1 and history is not None:
                from app.ui.pages.history import HistoryPage
                self.history_page = HistoryPage(history)
                self.stack.addWidget(self.history_page)
            elif idx == 2 and cfg is not None:
                from app.ui.pages.mapping import MappingPage
                self.mapping_page = MappingPage(cfg.mappings)
                self.stack.addWidget(self.mapping_page)
            elif idx == 3 and cfg is not None:
                from app.ui.pages.capture import CapturePage
                self.capture_page = CapturePage(cfg)
                self.stack.addWidget(self.capture_page)
            else:
                page = QLabel(f"{label} — placeholder")
                page.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.stack.addWidget(page)
        if cfg is not None:
            from app.ui.pages.settings import SettingsPage
            self.settings_page = SettingsPage(cfg)
            self.stack.addWidget(self.settings_page)
        else:
            self.settings_page = None
            page = QLabel(f"{NAV_ITEMS[4]} — placeholder")
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
        QShortcut(QKeySequence("F1"), self, activated=self._show_about)

    def _show_about(self):
        from app.ui.widgets.about import AboutDialog
        names = {}
        imgsz = 640
        AboutDialog(names, imgsz, self).exec()

    def _toggle_max(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def closeEvent(self, event):
        if getattr(self, "_force_quit", False):
            event.accept()
            return
        if getattr(self, "_minimize_to_tray", False) and getattr(self, "tray", None) is not None:
            event.ignore()
            self.hide()
        else:
            event.accept()

    def force_quit(self):
        self._force_quit = True
        self.close()
