"""Frameless main window: title bar + sidebar + stacked pages + status bar."""

from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
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


def _auto_heavy_page_load_enabled() -> bool:
    return QGuiApplication.platformName().lower() != "offscreen"


class MainWindow(QMainWindow):
    page_created = Signal(int, object)

    def __init__(self, cfg: AppConfig | None = None, history=None) -> None:
        super().__init__()
        self._cfg = cfg
        self._lazy_page_factories: dict[int, tuple[str, object]] = {}
        self._lazy_page_hosts: dict[int, tuple[QVBoxLayout, QWidget]] = {}
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
        self.settings_page = None
        self.system_log_page = SystemLogPage()
        self.stack.addWidget(self._stack_page(self.live_page))
        for idx, label in enumerate(NAV_ITEMS[1:5], start=1):
            if idx == 1 and history is not None:
                from app.ui.pages.history import HistoryPage

                self.history_page = HistoryPage(history)
                self.stack.addWidget(self._stack_page(self.history_page))
            elif idx == 2 and cfg is not None:
                self._add_lazy_page(idx, label, "mapping_page", self._create_mapping_page)
            elif idx == 3 and cfg is not None:
                self._add_lazy_page(idx, label, "capture_page", self._create_capture_page)
            elif idx == 4 and cfg is not None:
                self._add_lazy_page(idx, label, "training_page", self._create_training_page)
            else:
                page = EmptyState("○", label, "Runtime chưa nạp đủ dữ liệu cho màn này.")
                self.stack.addWidget(self._stack_page(page))
        # tab 4 = system log (always available, doesn't need cfg)
        self.stack.addWidget(self._stack_page(self.system_log_page))
        if cfg is not None:
            self._add_lazy_page(6, NAV_ITEMS[6], "settings_page", self._create_settings_page)
        else:
            page = EmptyState("⚙", NAV_ITEMS[6], "Runtime chưa nạp cấu hình, app vẫn chạy an toàn.")
            self.stack.addWidget(self._stack_page(page))
        self.sidebar.page_changed.connect(self.show_page)
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
        self._sync_responsive_shell()
        self._render_status()

        for i in range(len(NAV_ITEMS)):
            QShortcut(
                QKeySequence(f"Ctrl+{i + 1}"),
                self,
                activated=lambda i=i: (
                    self.sidebar.set_active(i),
                    self.show_page(i),
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
        self._sync_responsive_shell()
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

    def _add_lazy_page(
        self,
        index: int,
        label: str,
        attribute_name: str,
        factory,
    ) -> None:
        host = QWidget()
        host.setObjectName("workspace")
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        placeholder = EmptyState("○", label, "Mở mục này để tải dữ liệu.")
        layout.addWidget(placeholder)
        self._lazy_page_factories[index] = (attribute_name, factory)
        self._lazy_page_hosts[index] = (layout, placeholder)
        self.stack.addWidget(host)

    def ensure_page(self, index: int):
        page_info = self._lazy_page_factories.pop(index, None)
        if page_info is None:
            return self._page_for_index(index)
        attribute_name, factory = page_info
        page = factory()
        layout, placeholder = self._lazy_page_hosts.pop(index)
        scroll = self._stack_page(page)
        layout.replaceWidget(placeholder, scroll)
        placeholder.deleteLater()
        setattr(self, attribute_name, page)
        self.page_created.emit(index, page)
        return page

    def show_page(self, index: int) -> None:
        self.sidebar.set_active(index)
        self.ensure_page(index)
        if self.stack.currentIndex() == index:
            self._load_page(index)
            return
        self.stack.setCurrentIndex(index)

    def _page_for_index(self, index: int):
        return {
            0: self.live_page,
            1: self.history_page,
            2: self.mapping_page,
            3: self.capture_page,
            4: self.training_page,
            5: self.system_log_page,
            6: self.settings_page,
        }.get(index)

    def _create_mapping_page(self):
        from app.ui.pages.mapping import MappingPage

        assert self._cfg is not None
        return MappingPage(self._cfg.mappings)

    def _create_capture_page(self):
        from app.ui.pages.capture import CapturePage

        assert self._cfg is not None
        return CapturePage(self._cfg)

    def _create_training_page(self):
        from app.ui.pages.training import TrainingPage

        assert self._cfg is not None
        return TrainingPage(self._cfg)

    def _create_settings_page(self):
        from app.ui.pages.settings import SettingsPage

        assert self._cfg is not None
        return SettingsPage(self._cfg)

    def _on_stack_changed(self, index: int) -> None:
        self.sidebar.set_active(index)
        self.ensure_page(index)
        self._load_page(index)

    def _load_page(self, index: int) -> None:
        page = self._page_for_index(index)
        if index == 1 and page is not None:
            page.request_reload()
        elif index in {3, 4} and page is not None and _auto_heavy_page_load_enabled():
            page.load_once()

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

    def _sync_responsive_shell(self) -> None:
        width = self.width()
        if hasattr(self, "sidebar"):
            self.sidebar.set_compact(width < 1120)
        if hasattr(self, "title_bar"):
            self.title_bar.set_compact(width < 980)
        if hasattr(self, "status"):
            compact = width < 760
            self.status.setFixedHeight(36 if compact else 32)
            margin = 10 if compact else 16
            self.status.setContentsMargins(margin, 0, margin, 0)
            if hasattr(self, "_cam_ok"):
                self._render_status()

    def _render_status(self) -> None:
        def dot(ok: bool) -> str:
            color = "#10B981" if ok else "#EF4444"
            return f'<span style="color:{color}">●</span>'
        if self.width() < 760:
            self.status.setText(
                f"{dot(self._cam_ok)} Cam  &nbsp;•&nbsp;  "
                f"{dot(self._uart_ok)} UART  &nbsp;•&nbsp;  "
                f"{dot(self._model_ok)} AI  &nbsp;•&nbsp;  "
                f"{self._fps:.0f} FPS"
            )
            self.status.setTextFormat(Qt.TextFormat.RichText)
            return
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
