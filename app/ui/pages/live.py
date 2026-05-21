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
    QVBoxLayout,
    QWidget,
)

from app.core.events import Detection
from app.ui.widgets.stat_card import StatCard
from app.ui.widgets.video_view import VideoView


class LivePage(QWidget):
    pause_toggled = Signal(bool)
    snapshot_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paused = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Live Detection")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()
        self.btn_pause = QPushButton("⏸  Pause")
        self.btn_pause.setObjectName("secondary")
        self.btn_pause.clicked.connect(self._toggle_pause)
        self.btn_snap = QPushButton("📷  Snapshot")
        self.btn_snap.setObjectName("secondary")
        self.btn_snap.clicked.connect(self.snapshot_requested.emit)
        header.addWidget(self.btn_pause)
        header.addWidget(self.btn_snap)
        root.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(16)

        self.video = VideoView()
        body.addWidget(self.video, 3)

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
        # 3-column grid: 2 rows on narrow, 1 row on wide (Qt promotes equally)
        all_cards = [
            self.card_today, self.card_fps, self.card_latency,
            self.card_uart, self.card_total, self.card_acc,
        ]
        for i, c in enumerate(all_cards):
            cards.addWidget(c, i // 3, i % 3)
        for col in range(3):
            cards.setColumnStretch(col, 1)
        root.addLayout(cards)

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self.btn_pause.setText("▶  Resume" if self._paused else "⏸  Pause")
        self.pause_toggled.emit(self._paused)

    def is_paused(self) -> bool:
        return self._paused

    def update_frame(self, frame, detections: list[Detection]) -> None:
        if self._paused:
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
        self.card_fps.set_value(f"{fps:.0f}")

    def set_latency(self, ms: float) -> None:
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
