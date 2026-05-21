"""Live tab: video feed + detection stream + stat cards."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from app.core.events import Detection
from app.ui.widgets.stat_card import StatCard
from app.ui.widgets.video_view import VideoView


class LivePage(QWidget):
    pause_toggled = Signal(bool)
    snapshot_requested = Signal()
    camera_toggled = Signal(bool)  # True = bật, False = tắt

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paused = False
        self._cam_on = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Live Detection")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()
        self.btn_camera = QPushButton("▶  Bật camera")
        self.btn_camera.setObjectName("primary")
        self.btn_camera.setCheckable(True)
        self.btn_camera.clicked.connect(self._toggle_camera)
        self.btn_pause = QPushButton("⏸  Pause")
        self.btn_pause.setObjectName("secondary")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._toggle_pause)
        self.btn_snap = QPushButton("📷  Snapshot")
        self.btn_snap.setObjectName("secondary")
        self.btn_snap.setEnabled(False)
        self.btn_snap.clicked.connect(self.snapshot_requested.emit)
        header.addWidget(self.btn_camera)
        header.addWidget(self.btn_pause)
        header.addWidget(self.btn_snap)
        root.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(16)

        # video container with overlayed empty-state placeholder
        video_container = QWidget()
        self._video_stack = QStackedLayout(video_container)
        self._video_stack.setStackingMode(QStackedLayout.StackingMode.StackOne)

        self.video = VideoView()
        self._video_stack.addWidget(self.video)

        self.placeholder = QLabel("📷  Camera đang tắt")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet(
            "background: #000000; color: #475569; font-size: 14px;"
            " letter-spacing: 1px;"
        )
        self._video_stack.addWidget(self.placeholder)
        self._video_stack.setCurrentWidget(self.placeholder)

        body.addWidget(video_container, 3)

        self.stream = QListWidget()
        self.stream.setObjectName("card")
        self.stream.setMinimumWidth(280)
        self.stream.setStyleSheet("QListWidget { border-radius: 12px; padding: 8px; }")
        body.addWidget(self.stream, 1)

        root.addLayout(body, 1)

        cards = QGridLayout()
        cards.setSpacing(12)
        self.card_today = StatCard("TODAY", "0", "items")
        self.card_fps = StatCard("FPS", "0", "render")
        self.card_latency = StatCard("LATENCY", "0", "ms infer")
        self.card_uart = StatCard("UART", "—", "status")
        self.card_total = StatCard("TOTAL", "0", "all-time")
        self.card_acc = StatCard("AVG CONF", "0.00", "running")
        all_cards = [
            self.card_today, self.card_fps, self.card_latency,
            self.card_uart, self.card_total, self.card_acc,
        ]
        for i, c in enumerate(all_cards):
            cards.addWidget(c, i // 3, i % 3)
        for col in range(3):
            cards.setColumnStretch(col, 1)
        root.addLayout(cards)

    def _toggle_camera(self) -> None:
        self._cam_on = not self._cam_on
        self.set_camera_on(self._cam_on, emit=True)

    def set_camera_on(self, on: bool, emit: bool = False) -> None:
        """Update UI for camera on/off. emit=True propagates to controller."""
        self._cam_on = on
        self.btn_camera.blockSignals(True)
        self.btn_camera.setChecked(on)
        self.btn_camera.setText("⏹  Tắt camera" if on else "▶  Bật camera")
        self.btn_camera.setObjectName("secondary" if on else "primary")
        self.btn_camera.style().unpolish(self.btn_camera)
        self.btn_camera.style().polish(self.btn_camera)
        self.btn_camera.blockSignals(False)
        self.btn_pause.setEnabled(on)
        self.btn_snap.setEnabled(on)
        if on:
            self._video_stack.setCurrentWidget(self.video)
        else:
            self._video_stack.setCurrentWidget(self.placeholder)
            self._paused = False
            self.btn_pause.setText("⏸  Pause")
            self.card_fps.set_value("0")
            self.card_latency.set_value("0")
        if emit:
            self.camera_toggled.emit(on)

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self.btn_pause.setText("▶  Resume" if self._paused else "⏸  Pause")
        self.pause_toggled.emit(self._paused)

    def is_paused(self) -> bool:
        return self._paused

    def update_frame(self, frame, detections: list[Detection]) -> None:
        if self._paused or not self._cam_on:
            return
        # If the Live page itself isn't visible (user on another tab),
        # skip the QPixmap conversion + repaint entirely.
        if not self.isVisible():
            return
        self.video.set_frame(frame)
        self.video.set_detections(detections)

    def append_detection(self, cls_name: str, conf: float, ts: str) -> None:
        item = QListWidgetItem(f"●  {cls_name:<10} {conf:.2f}    {ts}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.stream.insertItem(0, item)
        while self.stream.count() > 50:
            self.stream.takeItem(self.stream.count() - 1)

    def set_fps(self, fps: float) -> None:
        if not self._cam_on:
            return
        self.card_fps.set_value(f"{fps:.0f}")

    def set_latency(self, ms: float) -> None:
        if not self._cam_on:
            return
        self.card_latency.set_value(f"{ms:.0f}")

    def set_today(self, n: int) -> None:
        self.card_today.set_value(str(n))

    def set_total(self, n: int) -> None:
        self.card_total.set_value(str(n))

    def set_uart_status(self, ok: bool) -> None:
        self.card_uart.set_value("OK" if ok else "OFF")
        self.card_uart.set_sub("connected" if ok else "disconnected")

    def set_avg_conf(self, conf: float) -> None:
        self.card_acc.set_value(f"{conf:.2f}")
