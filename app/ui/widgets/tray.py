"""System tray icon with menu and balloon notifications."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def _make_default_icon() -> QIcon:
    pix = QPixmap(32, 32)
    pix.fill("#10B981")
    return QIcon(pix)


class TrayIcon(QSystemTrayIcon):
    show_requested = Signal()
    pause_toggled = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None, icon: QIcon | None = None):
        super().__init__(icon or _make_default_icon(), parent)
        self.setToolTip("Trash Sorter Pro")
        menu = QMenu()
        act_show = QAction("Hiển thị", menu)
        act_show.triggered.connect(self.show_requested.emit)
        act_pause = QAction("Tạm dừng / Tiếp tục", menu)
        act_pause.triggered.connect(self.pause_toggled.emit)
        act_quit = QAction("Thoát", menu)
        act_quit.triggered.connect(self.quit_requested.emit)
        menu.addAction(act_show)
        menu.addAction(act_pause)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_requested.emit()

    def notify(self, title: str, message: str,
               level: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information):
        if QSystemTrayIcon.supportsMessages():
            self.showMessage(title, message, level, 4000)
