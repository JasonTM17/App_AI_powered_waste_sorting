"""Live tab: video feed, detection stream, and telemetry cards."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from app.core.events import Detection
from app.core.voice_pack import normalize_voice_gender, voice_gender_label, voice_pack_status
from app.ui.widgets.stat_card import StatCard
from app.ui.widgets.video_view import VideoView
from app.utils.paths import resource_path


def _icon(name: str) -> QIcon:
    path = resource_path(f"app/ui/resources/icons/{name}.svg")
    return QIcon(str(path)) if path.exists() else QIcon()


def _set_button_icon(button: QPushButton, name: str) -> None:
    button.setIcon(_icon(name))
    button.setIconSize(QSize(18, 18))


class LivePage(QWidget):
    pause_toggled = Signal(bool)
    snapshot_requested = Signal()
    camera_toggled = Signal(bool)
    actuation_test_mode_toggled = Signal(bool)
    speaker_output_mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paused = False
        self._cam_on = False
        self._uart_ok = False
        self._uart_protocol = ""
        self._actuation_test_mode = False
        self._dispatch_status = ""
        self._speaker_output_mode = "hardware"
        self._speaker_voice_gender = "female"

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(16)

        header = QVBoxLayout()
        header.setSpacing(10)
        title_row = QHBoxLayout()
        title = QLabel("Live Detection")
        title.setObjectName("h1")
        title.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        title_row.addWidget(title)
        title_row.addStretch()
        header.addLayout(title_row)

        from app.ui.widgets.flow_layout import FlowLayout
        controls = FlowLayout(margin=0, h_spacing=12, v_spacing=12)

        self.btn_camera = QPushButton("Bật camera")
        self.btn_camera.setObjectName("primary")
        self.btn_camera.setCheckable(True)
        self.btn_camera.setMinimumWidth(128)
        self.btn_camera.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        _set_button_icon(self.btn_camera, "play")
        self.btn_camera.clicked.connect(self._toggle_camera)

        self.btn_actuation = QPushButton("Bật gửi Arduino")
        self.btn_actuation.setObjectName("secondary")
        self.btn_actuation.setCheckable(True)
        self.btn_actuation.setMinimumWidth(150)
        self.btn_actuation.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.btn_actuation.setToolTip(
            "Bật công tắc này mới cho phép app gửi lệnh phân loại xuống Arduino."
        )
        _set_button_icon(self.btn_actuation, "hardware")
        self.btn_actuation.clicked.connect(self._toggle_actuation_test_mode)

        self.dispatch_mode_label = QLabel("")
        self.dispatch_mode_label.setMinimumWidth(150)
        self.dispatch_mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dispatch_mode_label.setToolTip(
            "Trạng thái gửi lệnh phân loại xuống Arduino khi AI nhận diện rác."
        )

        self.btn_pause = QPushButton("Tạm dừng")
        self.btn_pause.setObjectName("secondary")
        self.btn_pause.setEnabled(False)
        self.btn_pause.setMinimumWidth(96)
        self.btn_pause.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        _set_button_icon(self.btn_pause, "pause")
        self.btn_pause.clicked.connect(self._toggle_pause)

        self.btn_snap = QPushButton("Chụp ảnh")
        self.btn_snap.setObjectName("secondary")
        self.btn_snap.setEnabled(False)
        self.btn_snap.setMinimumWidth(112)
        self.btn_snap.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        _set_button_icon(self.btn_snap, "snapshot")
        self.btn_snap.clicked.connect(self.snapshot_requested.emit)

        controls.addWidget(self.btn_camera)
        controls.addWidget(self.btn_actuation)
        controls.addWidget(self.dispatch_mode_label)
        controls.addWidget(self.btn_pause)
        controls.addWidget(self.btn_snap)
        header.addLayout(controls)

        self.dispatch_status_detail = QLabel("")
        self.dispatch_status_detail.setObjectName("muted")
        self.dispatch_status_detail.setWordWrap(True)
        header.addWidget(self.dispatch_status_detail)
        root.addLayout(header)

        speaker_bar = QFrame()
        speaker_bar.setObjectName("toolbar")
        speaker_layout = QHBoxLayout(speaker_bar)
        speaker_layout.setContentsMargins(16, 10, 16, 10)
        speaker_layout.setSpacing(10)
        speaker_label = QLabel("Loa")
        speaker_label.setObjectName("mono")
        speaker_layout.addWidget(speaker_label)
        self._speaker_group = QButtonGroup(self)
        self._speaker_group.setExclusive(True)
        self.btn_hw_speaker = QPushButton("Loa phần cứng")
        self.btn_hw_speaker.setCheckable(True)
        self.btn_hw_speaker.setObjectName("segmented")
        self.btn_hw_speaker.setIcon(_icon("hardware"))
        self.btn_hw_speaker.setIconSize(QSize(18, 18))
        self.btn_hw_speaker.clicked.connect(
            lambda: self.set_speaker_output_mode("hardware", emit=True)
        )
        self.btn_pc_speaker = QPushButton("Loa laptop")
        self.btn_pc_speaker.setCheckable(True)
        self.btn_pc_speaker.setObjectName("segmented")
        self.btn_pc_speaker.setIcon(_icon("speaker"))
        self.btn_pc_speaker.setIconSize(QSize(18, 18))
        self.btn_pc_speaker.clicked.connect(
            lambda: self.set_speaker_output_mode("computer_speaker", emit=True)
        )
        self._speaker_group.addButton(self.btn_hw_speaker, 0)
        self._speaker_group.addButton(self.btn_pc_speaker, 1)
        speaker_layout.addWidget(self.btn_hw_speaker)
        speaker_layout.addWidget(self.btn_pc_speaker)
        self.speaker_status = QLabel("")
        self.speaker_status.setObjectName("muted")
        self.speaker_status.setWordWrap(True)
        speaker_layout.addWidget(self.speaker_status, 1)
        root.addWidget(speaker_bar)

        self.warning = QLabel("")
        self.warning.setObjectName("warning-banner")
        self.warning.setWordWrap(True)
        self.warning.setVisible(False)
        root.addWidget(self.warning)

        body = QHBoxLayout()
        body.setSpacing(16)

        video_card = QFrame()
        video_card.setObjectName("card")
        video_layout = QVBoxLayout(video_card)
        video_layout.setContentsMargins(16, 14, 16, 16)
        video_layout.setSpacing(12)
        video_title = QLabel("LIVE CAMERA")
        video_title.setObjectName("mono")
        video_layout.addWidget(video_title)

        video_container = QWidget()
        video_container.setMinimumHeight(360)
        self._video_stack = QStackedLayout(video_container)
        self._video_stack.setStackingMode(QStackedLayout.StackingMode.StackOne)

        self.video = VideoView()
        self._video_stack.addWidget(self.video)

        self.placeholder = QLabel("Camera đang tắt")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet(
            "background: #060E20; color: #86948A; font-size: 14px;"
            " border-radius: 12px; letter-spacing: 1px;"
        )
        self._video_stack.addWidget(self.placeholder)
        self._video_stack.setCurrentWidget(self.placeholder)
        video_layout.addWidget(video_container, 1)

        body.addWidget(video_card, 3)

        stream_card = QFrame()
        stream_card.setObjectName("card")
        stream_layout = QVBoxLayout(stream_card)
        stream_layout.setContentsMargins(16, 14, 16, 16)
        stream_layout.setSpacing(12)
        stream_title = QLabel("AI DETECTION")
        stream_title.setObjectName("mono")
        stream_layout.addWidget(stream_title)
        self.stream = QListWidget()
        self.stream.setMinimumWidth(260)
        stream_layout.addWidget(self.stream, 1)
        body.addWidget(stream_card, 1)

        root.addLayout(body, 1)

        cards = FlowLayout(margin=0, h_spacing=12, v_spacing=12)
        self.card_today = StatCard("TODAY", "0", "items")
        self.card_fps = StatCard("FPS", "0", "render")
        self.card_latency = StatCard("LATENCY", "0", "ms infer")
        self.card_uart = StatCard("UART", "OFF", "disconnected")
        self.card_total = StatCard("TOTAL", "0", "all-time")
        self.card_acc = StatCard("AVG CONF", "0.00", "running")
        all_cards = [
            self.card_today,
            self.card_fps,
            self.card_latency,
            self.card_uart,
            self.card_total,
            self.card_acc,
        ]
        for c in all_cards:
            cards.addWidget(c)
        root.addLayout(cards)
        self.set_speaker_output_mode("hardware")
        self.set_actuation_test_mode(False)

    def _toggle_camera(self) -> None:
        self._cam_on = not self._cam_on
        self.set_camera_on(self._cam_on, emit=True)

    def set_camera_on(self, on: bool, emit: bool = False) -> None:
        """Update UI for camera on/off. emit=True propagates to controller."""
        self._cam_on = on
        self.btn_camera.blockSignals(True)
        self.btn_camera.setChecked(on)
        self.btn_camera.setText("Tắt camera" if on else "Bật camera")
        self.btn_camera.setObjectName("secondary" if on else "primary")
        _set_button_icon(self.btn_camera, "stop" if on else "play")
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
            self.btn_pause.setText("Tạm dừng")
            _set_button_icon(self.btn_pause, "pause")
            self.card_fps.set_value("0")
            self.card_latency.set_value("0")
        if emit:
            self.camera_toggled.emit(on)

    def set_warning(self, text: str) -> None:
        message = str(text or "").strip()
        self.warning.setText(message)
        self.warning.setVisible(bool(message))

    def set_speaker_output_mode(self, mode: str, emit: bool = False) -> None:
        normalized = "computer_speaker" if str(mode or "").strip() == "computer_speaker" else "hardware"
        self._speaker_output_mode = normalized
        self.btn_hw_speaker.blockSignals(True)
        self.btn_pc_speaker.blockSignals(True)
        self.btn_hw_speaker.setChecked(normalized == "hardware")
        self.btn_pc_speaker.setChecked(normalized == "computer_speaker")
        self.btn_hw_speaker.blockSignals(False)
        self.btn_pc_speaker.blockSignals(False)
        self.speaker_status.setText(self._speaker_status_text())
        if emit:
            self.speaker_output_mode_changed.emit(normalized)

    def set_speaker_voice_gender(self, gender: str) -> None:
        self._speaker_voice_gender = normalize_voice_gender(gender)
        self.speaker_status.setText(self._speaker_status_text())

    def _speaker_status_text(self) -> str:
        status = voice_pack_status(self._speaker_voice_gender)
        ready = sum(1 for ok in status.values() if ok)
        total = len(status)
        missing = [name for name, ok in status.items() if not ok]
        label = voice_gender_label(self._speaker_voice_gender)
        if self._speaker_output_mode == "computer_speaker":
            if not missing:
                return f"Loa laptop {label}: sẵn sàng ({ready}/{total} file)."
            return f"Loa laptop {label}: thiếu {len(missing)} file: {', '.join(missing)}."
        if not missing:
            return f"Loa phần cứng đang ưu tiên. Loa laptop {label} sẵn sàng ({ready}/{total} file)."
        return f"Loa phần cứng đang ưu tiên. Loa laptop {label} thiếu {len(missing)} file: {', '.join(missing)}."

    def _toggle_actuation_test_mode(self, checked: bool) -> None:
        self.set_actuation_test_mode(bool(checked), emit=True)

    def set_actuation_test_mode(self, enabled: bool, emit: bool = False) -> None:
        self._actuation_test_mode = bool(enabled)
        if self._actuation_test_mode and not self._uart_ok:
            self.set_warning("UART chưa kết nối, lệnh phân loại sẽ không được gửi xuống phần cứng.")
        elif not self._actuation_test_mode:
            self.set_warning("")
        self.btn_actuation.blockSignals(True)
        self.btn_actuation.setChecked(self._actuation_test_mode)
        self.btn_actuation.setText(
            "Dừng gửi Arduino" if self._actuation_test_mode else "Bật gửi Arduino"
        )
        self.btn_actuation.setObjectName("danger" if self._actuation_test_mode else "secondary")
        _set_button_icon(self.btn_actuation, "hardware")
        self.btn_actuation.style().unpolish(self.btn_actuation)
        self.btn_actuation.style().polish(self.btn_actuation)
        self.btn_actuation.blockSignals(False)
        self._sync_dispatch_mode_label()
        if emit:
            self.actuation_test_mode_toggled.emit(self._actuation_test_mode)

    def set_dispatch_status(self, status: str) -> None:
        self._dispatch_status = str(status or "").strip()
        self._sync_dispatch_mode_label()

    def _sync_dispatch_mode_label(self) -> None:
        if self._actuation_test_mode:
            if self._uart_ok:
                self.dispatch_mode_label.setText("Gửi xuống Arduino")
                detail = "Đã bật gửi lệnh; ROI, mapping và guard vẫn quyết định từng lần gửi."
                if self._uart_protocol == "plain_group":
                    detail += " Format: huuco / voco / taiche."
                elif self._uart_protocol == "sort_line":
                    detail += " Format: SORT:<cmd>:<conf>."
            else:
                self.dispatch_mode_label.setText("Chờ UART")
                detail = "Đã bật gửi nhưng chưa thấy Arduino/COM; app chưa gửi được lệnh thật."
            self.dispatch_mode_label.setStyleSheet(
                "padding: 6px 10px; border-radius: 6px;"
                " color: #FBBF24; border: 1px solid rgba(251,191,36,0.42);"
                " background: rgba(251,191,36,0.10); font-weight: 700;"
            )
        else:
            self.dispatch_mode_label.setText("Chỉ nhận diện")
            detail = "Không gửi lệnh xuống Arduino. Bật gửi Arduino chỉ khi đã kiểm tra ROI và mapping."
            self.dispatch_mode_label.setStyleSheet(
                "padding: 6px 10px; border-radius: 6px;"
                " color: #67E8F9; border: 1px solid rgba(103,232,249,0.32);"
                " background: rgba(103,232,249,0.08); font-weight: 700;"
            )
        if self._dispatch_status:
            detail = f"{detail} Trạng thái guard: {self._dispatch_status}."
        self.dispatch_status_detail.setText(detail)

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self.btn_pause.setText("Tiếp tục" if self._paused else "Tạm dừng")
        _set_button_icon(self.btn_pause, "play" if self._paused else "pause")
        self.pause_toggled.emit(self._paused)

    def is_paused(self) -> bool:
        return self._paused

    def update_frame(self, frame, detections: list[Detection]) -> None:
        if self._paused or not self._cam_on:
            return
        if not self.isVisible():
            return
        self.video.set_frame(frame)
        self.video.set_detections(detections)

    def append_detection(self, cls_name: str, conf: float, ts: str, detail: str = "") -> None:
        suffix = f"\n    {detail}" if detail else ""
        item = QListWidgetItem(f"*  {cls_name:<10} {conf:.2f}    {ts}{suffix}")
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

    def set_uart_status(self, ok: bool, protocol: str = "") -> None:
        self._uart_ok = bool(ok)
        self._uart_protocol = protocol
        self.card_uart.set_value("OK" if ok else "OFF")
        self.card_uart.set_sub("connected" if ok else "disconnected")
        self._sync_dispatch_mode_label()

    def set_avg_conf(self, conf: float) -> None:
        self.card_acc.set_value(f"{conf:.2f}")
