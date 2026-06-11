"""Frameless main window: title bar + sidebar + stacked pages + status bar."""

from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.config import AppConfig
from app.ui.brand_assets import brand_icon
from app.ui.widgets.empty_state import EmptyState
from app.ui.widgets.sidebar import Sidebar
from app.ui.widgets.title_bar import TitleBar

NAV_ITEMS = ["Live", "Lịch sử", "Mapping", "Data", "Huấn luyện", "Nhật ký", "Cài đặt"]
NAV_ICONS = ["recycle", "history", "mapping", "capture", "camera", "log", "settings"]


class MainWindow(QMainWindow):
    def __init__(self, cfg: AppConfig | None = None, history=None) -> None:
        super().__init__()
        self.setWindowIcon(brand_icon())
        self._force_quit = False
        self._minimize_to_tray = False
        self._initial_geometry_done = False
        self._user_minimized = False
        self._was_maximized_before_minimize = False
        self.tray = None
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._resize_to_available_screen()

        root = QWidget()
        root.setObjectName("workspace")
        self.setCentralWidget(root)

        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QWidget()
        body.setObjectName("workspace")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = Sidebar(NAV_ITEMS, icons=NAV_ICONS, theme=cfg.theme if cfg is not None else "dark")
        outer.addWidget(self.sidebar)

        self.title_bar = TitleBar("Trash Sorter Pro")
        self.title_bar.minimize_requested.connect(self._minimize_window)
        self.title_bar.maximize_toggled.connect(self._toggle_max)
        self.title_bar.close_requested.connect(self.close)
        body_layout.addWidget(self.title_bar)

        from app.ui.pages.live import LivePage
        from app.ui.pages.system_log import SystemLogPage

        self.stack = QStackedWidget()
        self.stack.setObjectName("workspace")
        self.live_page = LivePage()
        self.mapping_page = None
        self.history_page = None
        self.capture_page = None
        self.training_page = None
        self.system_log_page = SystemLogPage()
        self.stack.addWidget(self._stack_page(self.live_page))
        for idx, label in enumerate(NAV_ITEMS[1:5], start=1):
            if idx == 1 and history is not None:
                from app.ui.pages.history import HistoryPage

                self.history_page = HistoryPage(history)
                self.stack.addWidget(self._stack_page(self.history_page))
            elif idx == 2 and cfg is not None:
                from app.ui.pages.mapping import MappingPage

                self.mapping_page = MappingPage(cfg.mappings)
                self.stack.addWidget(self._stack_page(self.mapping_page))
            elif idx == 3 and cfg is not None:
                from app.ui.pages.capture import CapturePage

                self.capture_page = CapturePage(cfg)
                self.stack.addWidget(self._stack_page(self.capture_page))
            elif idx == 4 and cfg is not None:
                from app.ui.pages.training import TrainingPage

                self.training_page = TrainingPage(cfg)
                self.stack.addWidget(self._stack_page(self.training_page))
            else:
                page = EmptyState("○", label, "Runtime chưa nạp đủ dữ liệu cho màn này.")
                self.stack.addWidget(self._stack_page(page))
        # tab 4 = system log (always available, doesn't need cfg)
        self.stack.addWidget(self._stack_page(self.system_log_page))
        if cfg is not None:
            from app.ui.pages.settings import SettingsPage

            self.settings_page = SettingsPage(cfg)
            self.stack.addWidget(self._stack_page(self.settings_page))
        else:
            self.settings_page = None
            page = EmptyState("⚙", NAV_ITEMS[6], "Runtime chưa nạp cấu hình, app vẫn chạy an toàn.")
            self.stack.addWidget(self._stack_page(page))
        self.sidebar.page_changed.connect(self.stack.setCurrentIndex)
        self.stack.currentChanged.connect(self._on_stack_changed)

        body_layout.addWidget(self.stack, 1)

        self.status = QLabel("● Camera —  •  ● UART —  •  ● Model —  •  FPS 0  ")
        self.status.setObjectName("statusbar")
        self.status.setFixedHeight(32)
        self.status.setContentsMargins(16, 0, 16, 0)
        body_layout.addWidget(self.status)
        outer.addWidget(body, 1)
        self._cam_ok = False
        self._uart_ok = False
        self._model_ok = False
        self._fps = 0.0

        for i in range(len(NAV_ITEMS)):
            QShortcut(
                QKeySequence(f"Ctrl+{i + 1}"),
                self,
                activated=lambda i=i: (
                    self.sidebar.set_active(i),
                    self.stack.setCurrentIndex(i),
                ),
            )
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.close)
        QShortcut(QKeySequence("F1"), self, activated=self._show_about)

        self._grip_br = QSizeGrip(self)
        self._grip_bl = QSizeGrip(self)
        self._grip_br.setFixedSize(16, 16)
        self._grip_bl.setFixedSize(16, 16)
        self._grip_br.setStyleSheet("background: transparent;")
        self._grip_bl.setStyleSheet("background: transparent;")
        self._grip_br.raise_()
        self._grip_bl.raise_()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "_grip_br"):
            self._grip_br.move(self.width() - 16, self.height() - 16)
            self._grip_bl.move(0, self.height() - 16)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        if not self._initial_geometry_done and not self.isMaximized():
            self._initial_geometry_done = True
            QTimer.singleShot(0, lambda: self._ensure_on_screen(center=True))

    def changeEvent(self, event):  # noqa: N802
        super().changeEvent(event)
        if event.type() != QEvent.Type.WindowStateChange:
            return
        if self.isMinimized():
            self._user_minimized = True
            return
        if not self.isMinimized():
            self._user_minimized = False
            QTimer.singleShot(0, self._ensure_on_screen)

    def nativeEvent(self, event_type, message):  # noqa: N802
        if sys.platform == "win32" and event_type == "windows_generic_MSG":
            try:
                from ctypes import wintypes

                msg = wintypes.MSG.from_address(int(message))
                if msg.message == 0x0112:
                    command = int(msg.wParam) & 0xFFF0
                    if command == 0xF020:  # SC_MINIMIZE from taskbar/system menu.
                        self._user_minimized = True
                    elif command == 0xF120:  # SC_RESTORE from taskbar/system menu.
                        self._user_minimized = False
                        QTimer.singleShot(0, self.restore_window)
            except Exception:
                pass
        return super().nativeEvent(event_type, message)

    def _show_about(self):
        from app.ui.widgets.about import AboutDialog

        names = {}
        imgsz = 640
        AboutDialog(names, imgsz, self).exec()

    def _toggle_max(self) -> None:
        if self.isMaximized():
            self.showNormal()
            QTimer.singleShot(0, self._ensure_on_screen)
        else:
            self.showMaximized()

    def _stack_page(self, page: QWidget) -> QScrollArea:
        page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        scroll = QScrollArea()
        scroll.setObjectName("workspace")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(page)
        return scroll

    def _on_stack_changed(self, index: int) -> None:
        if index == 1 and self.history_page is not None:
            self.history_page.request_reload()
        elif index == 3 and self.capture_page is not None:
            self.capture_page.load_once()
        elif index == 4 and self.training_page is not None:
            self.training_page.load_once()

    def _minimize_window(self) -> None:
        self._user_minimized = True
        self._was_maximized_before_minimize = self.isMaximized()
        self.showMinimized()

    def restore_window(self) -> None:
        self._user_minimized = False
        self._native_restore_window()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        if self._was_maximized_before_minimize:
            self.showMaximized()
        else:
            self.showNormal()
        QTimer.singleShot(0, self._ensure_on_screen)
        QTimer.singleShot(100, self._ensure_on_screen)
        self.raise_()
        self.activateWindow()
        self._native_restore_window()
        self._was_maximized_before_minimize = False

    def _native_restore_window(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes

            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            user32.ShowWindowAsync.argtypes = [ctypes.c_void_p, ctypes.c_int]
            user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
            handle = ctypes.c_void_p(hwnd)
            user32.ShowWindowAsync(handle, 1)  # SW_SHOWNORMAL
            user32.ShowWindowAsync(handle, 9)  # SW_RESTORE
            user32.SetForegroundWindow(handle)
        except Exception:
            return

    def _resize_to_available_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(1366, 860)
            return
        available = screen.availableGeometry()
        width = min(1440, max(960, available.width() - 96), available.width())
        height = min(900, max(680, available.height() - 96), available.height())
        self.resize(width, height)

    def _ensure_on_screen(self, center: bool = False) -> None:
        screen = QGuiApplication.screenAt(self.frameGeometry().center())
        screen = screen or QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        if self.width() > available.width() or self.height() > available.height():
            self.resize(
                max(1, min(self.width(), available.width())),
                max(1, min(self.height(), available.height())),
            )
        frame = self.frameGeometry()
        if center:
            frame.moveCenter(available.center())
        max_x = max(available.left(), available.right() - frame.width() + 1)
        max_y = max(available.top(), available.bottom() - frame.height() + 1)
        x = min(max(frame.x(), available.left()), max_x)
        y = min(max(frame.y(), available.top()), max_y)
        self.move(x, y)

    def ensure_visible_on_screen(self, *, center: bool = False) -> None:
        self._ensure_on_screen(center=center)

    def closeEvent(self, event):  # noqa: N802
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

    def _render_status(self) -> None:
        def dot(ok: bool) -> str:
            color = "#10B981" if ok else "#EF4444"
            return f'<span style="color:{color}">●</span>'
        self.status.setText(
            f"{dot(self._cam_ok)} Camera  &nbsp;•&nbsp;  "
            f"{dot(self._uart_ok)} UART  &nbsp;•&nbsp;  "
            f"{dot(self._model_ok)} Model  &nbsp;•&nbsp;  "
            f"FPS {self._fps:.0f}  "
        )
        self.status.setTextFormat(Qt.TextFormat.RichText)

    def set_camera_status(self, ok: bool) -> None:
        self._cam_ok = ok
        self._render_status()

    def set_uart_status(self, ok: bool) -> None:
        self._uart_ok = ok
        self._render_status()
        if hasattr(self, "live_page") and self.live_page is not None:
            self.live_page.set_uart_status(ok)

    def set_model_status(self, ok: bool) -> None:
        self._model_ok = ok
        self._render_status()

    def set_fps(self, fps: float) -> None:
        self._fps = fps
        self._render_status()
