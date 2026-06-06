"""Custom frameless window title bar."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from app.utils.paths import resource_path


class TitleBar(QWidget):
    minimize_requested = Signal()
    maximize_toggled = Signal()
    close_requested = Signal()
    camera_toggled = Signal(bool)  # True = bật, False = tắt
    web_requested = Signal()

    def __init__(self, title: str = "Trash Sorter Pro", parent=None):
        super().__init__(parent)
        self.setObjectName("titlebar")
        self.setFixedHeight(40)
        self._drag_offset: QPoint | None = None
        self._cam_on = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(8)

        logo_path = resource_path("app/ui/resources/icons/logo.svg")
        self.logo = QLabel()
        if logo_path.exists():
            pix = QIcon(str(logo_path)).pixmap(QSize(22, 22))
            self.logo.setPixmap(pix)
        self.logo.setFixedSize(24, 40)
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.logo)

        self.label = QLabel(title)
        self.label.setObjectName("titlebar-label")
        layout.addWidget(self.label)
        layout.addStretch()

        self.btn_web = QPushButton("🌐  Mở Web")
        self.btn_web.setObjectName("titlebar-secondary")
        self.btn_web.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_web.setFixedHeight(28)
        self.btn_web.clicked.connect(self.web_requested.emit)
        layout.addWidget(self.btn_web)

        self.btn_camera = QPushButton("▶  Bật camera")
        self.btn_camera.setObjectName("titlebar-cta")
        self.btn_camera.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_camera.setFixedHeight(28)
        self.btn_camera.clicked.connect(self._on_camera_clicked)
        layout.addWidget(self.btn_camera)
        layout.addSpacing(12)

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

    def _on_camera_clicked(self) -> None:
        self.set_camera_on(not self._cam_on, emit=True)

    def set_camera_on(self, on: bool, emit: bool = False) -> None:
        self._cam_on = on
        self.btn_camera.setText("⏹  Tắt camera" if on else "▶  Bật camera")
        # toggle property so QSS can theme on/off states
        self.btn_camera.setProperty("active", on)
        self.btn_camera.style().unpolish(self.btn_camera)
        self.btn_camera.style().polish(self.btn_camera)
        if emit:
            self.camera_toggled.emit(on)

    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton and self.window() is not None:
            self._drag_offset = e.globalPosition().toPoint() - self.window().pos()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
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

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        self._drag_offset = None

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        self.maximize_toggled.emit()
