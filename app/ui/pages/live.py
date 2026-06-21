"""Live tab: video feed, detection stream, and telemetry cards."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QBoxLayout,
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

from app.core.detection_display_stabilizer import DetectionDisplayStabilizer
from app.core.events import Detection
from app.core.voice_pack import normalize_voice_gender, voice_pack_status
from app.ui.widgets.stat_card import StatCard
from app.ui.widgets.video_view import VideoView
from app.utils.paths import resource_path

LIVE_CONTROL_SIZE = QSize(176, 56)
SPEAKER_BUTTON_SIZE = QSize(182, 48)
DETECTION_STREAM_LIMIT = 50
BATTERY_WARNING_TEXT = (
    "Đây là rác thải nguy hại. Nếu muốn đổ, hãy xác nhận để đưa pin vào Vô cơ."
)


def _icon(name: str) -> QIcon:
    path = resource_path(f"app/ui/resources/icons/{name}.svg")
    return QIcon(str(path)) if path.exists() else QIcon()


def _set_button_icon(button: QPushButton, name: str) -> None:
    button.setIcon(_icon(name))
    button.setIconSize(QSize(18, 18))


def _mark_live_action_button(button: QPushButton) -> None:
    button.setProperty("liveAction", True)
    button.setFixedSize(LIVE_CONTROL_SIZE)
    button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


def _dispatch_pill_style(*, color: str, border: str, background: str) -> str:
    return (
        "padding: 0;"
        "border-radius: 8px;"
        "font-size: 14px;"
        "font-weight: 700;"
        f"color: {color};"
        f"border: 1px solid {border};"
        f"background: {background};"
    )


class LivePage(QWidget):
    pause_toggled = Signal(bool)
    snapshot_requested = Signal()
    camera_toggled = Signal(bool)
    actuation_test_mode_toggled = Signal(bool)
    speaker_output_mode_changed = Signal(str)
    hazardous_battery_confirmation_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paused = False
        self._cam_on = False
        self._uart_ok = False
        self._uart_protocol = ""
        self._actuation_test_mode = False
        self._dispatch_status = ""
        self._auto_sort_state = "WAITING_EMPTY"
        self._speaker_output_mode = "hardware"
        self._speaker_voice_gender = "female"
        self._battery_confirmation_pending = False
        self._display_stabilizer = DetectionDisplayStabilizer(
            window_size=9,
            acquire_frames=3,
            switch_frames=6,
            switch_consecutive_frames=3,
            group_by_route=True,
            exact_acquire_frames=4,
            exact_switch_frames=6,
            exact_switch_consecutive_frames=3,
        )

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
        self._controls_layout = controls

        self.btn_camera = QPushButton("Bật camera")
        self.btn_camera.setObjectName("primary")
        self.btn_camera.setCheckable(True)
        _mark_live_action_button(self.btn_camera)
        _set_button_icon(self.btn_camera, "play")
        self.btn_camera.clicked.connect(self._toggle_camera)

        self.btn_actuation = QPushButton("Bật phân loại tự động")
        self.btn_actuation.setObjectName("secondary")
        self.btn_actuation.setCheckable(True)
        _mark_live_action_button(self.btn_actuation)
        self.btn_actuation.setToolTip(
            "Bật một lần để app tự nhận diện, đổ rác và phát âm thanh cho từng vật."
        )
        _set_button_icon(self.btn_actuation, "hardware")
        self.btn_actuation.clicked.connect(self._toggle_actuation_test_mode)

        self.dispatch_mode_label = QLabel("")
        self.dispatch_mode_label.setFixedSize(LIVE_CONTROL_SIZE)
        self.dispatch_mode_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.dispatch_mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dispatch_mode_label.setToolTip(
            "Trạng thái gửi lệnh phân loại xuống Arduino khi AI nhận diện rác."
        )

        self.btn_pause = QPushButton("Tạm dừng")
        self.btn_pause.setObjectName("secondary")
        self.btn_pause.setEnabled(False)
        _mark_live_action_button(self.btn_pause)
        _set_button_icon(self.btn_pause, "pause")
        self.btn_pause.clicked.connect(self._toggle_pause)

        self.btn_snap = QPushButton("Chụp ảnh")
        self.btn_snap.setObjectName("secondary")
        self.btn_snap.setEnabled(False)
        _mark_live_action_button(self.btn_snap)
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
        self.btn_hw_speaker.setFixedSize(SPEAKER_BUTTON_SIZE)
        self.btn_hw_speaker.setIcon(_icon("hardware"))
        self.btn_hw_speaker.setIconSize(QSize(18, 18))
        self.btn_hw_speaker.clicked.connect(
            lambda: self.set_speaker_output_mode("hardware", emit=True)
        )
        self.btn_pc_speaker = QPushButton("Loa laptop")
        self.btn_pc_speaker.setCheckable(True)
        self.btn_pc_speaker.setObjectName("segmented")
        self.btn_pc_speaker.setFixedSize(SPEAKER_BUTTON_SIZE)
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
        self.speaker_status.setVisible(False)
        speaker_layout.addWidget(self.speaker_status, 1)
        root.addWidget(speaker_bar)

        self.warning = QLabel("")
        self.warning.setObjectName("warning-banner")
        self.warning.setWordWrap(True)
        self.warning.setVisible(False)
        root.addWidget(self.warning)

        self.battery_warning = QFrame()
        self.battery_warning.setObjectName("warning-banner")
        battery_layout = QHBoxLayout(self.battery_warning)
        battery_layout.setContentsMargins(14, 10, 14, 10)
        battery_layout.setSpacing(12)
        self.battery_warning_text = QLabel(
            "Đây là rác thải nguy hại không thuộc 3 loại rác này. "
            "Nếu muốn đổ thì tôi sẽ đổ vào Vô cơ, nhưng đây là loại rác nguy hiểm nên bạn hãy lưu ý nhé."
        )
        self.battery_warning_text.setWordWrap(True)
        battery_layout.addWidget(self.battery_warning_text, 1)
        self.btn_confirm_battery = QPushButton("Xác nhận đưa vào Vô cơ")
        self.btn_confirm_battery.setObjectName("danger")
        self.btn_confirm_battery.setToolTip("Chỉ gửi pin vào thùng Vô cơ sau khi Admin xác nhận.")
        self.btn_confirm_battery.clicked.connect(
            self._request_hazardous_battery_confirmation
        )
        battery_layout.addWidget(self.btn_confirm_battery)
        self.battery_warning.setVisible(False)
        root.addWidget(self.battery_warning)

        body = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._body_layout = body
        body.setSpacing(16)

        video_card = QFrame()
        video_card.setObjectName("card")
        video_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_card = video_card
        video_layout = QVBoxLayout(video_card)
        video_layout.setContentsMargins(16, 14, 16, 16)
        video_layout.setSpacing(12)
        video_title = QLabel("LIVE CAMERA")
        video_title.setObjectName("mono")
        video_layout.addWidget(video_title)

        video_container = QWidget()
        video_container.setMinimumHeight(320)
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

        body.addWidget(video_card, 4)

        stream_card = QFrame()
        stream_card.setObjectName("card")
        stream_card.setMinimumWidth(220)
        stream_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._stream_card = stream_card
        stream_layout = QVBoxLayout(stream_card)
        stream_layout.setContentsMargins(16, 14, 16, 16)
        stream_layout.setSpacing(12)
        stream_title = QLabel("KẾT QUẢ HIỆN TẠI")
        stream_title.setObjectName("mono")
        stream_layout.addWidget(stream_title)
        self.stream = QListWidget()
        self.stream.setMinimumWidth(0)
        self.stream.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stream.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self.stream.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.stream.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.stream.setWordWrap(True)
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
        self._sync_responsive_body()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._sync_responsive_body()

    def _sync_responsive_body(self) -> None:
        if not hasattr(self, "_body_layout"):
            return
        narrow = self.width() < 820
        direction = QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight
        if self._body_layout.direction() != direction:
            self._body_layout.setDirection(direction)
        self._stream_card.setMaximumHeight(260 if narrow else 16777215)
        self._stream_card.setMaximumWidth(16777215)

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
            self._display_stabilizer.reset()
            self.stream.clear()
            self._paused = False
            self.btn_pause.setText("Tạm dừng")
            _set_button_icon(self.btn_pause, "pause")
            self.card_fps.set_value("0")
            self.card_latency.set_value("0")
            self.set_hazardous_battery_warning(False)
        if emit:
            self.camera_toggled.emit(on)

    def set_warning(self, text: str) -> None:
        message = str(text or "").strip()
        self.warning.setText(message)
        self.warning.setVisible(bool(message))

    def set_hazardous_battery_warning(self, active: bool) -> None:
        self.battery_warning.setVisible(bool(active))
        if not active:
            self._battery_confirmation_pending = False
            self.btn_confirm_battery.setText("Xác nhận đưa vào Vô cơ")
            self.battery_warning_text.setText(BATTERY_WARNING_TEXT)
        self.btn_confirm_battery.setEnabled(
            bool(
                active
                and self._actuation_test_mode
                and self._uart_ok
                and not self._battery_confirmation_pending
            )
        )

    def _request_hazardous_battery_confirmation(self) -> None:
        self._battery_confirmation_pending = True
        self.btn_confirm_battery.setEnabled(False)
        self.btn_confirm_battery.setText("Đang xác nhận...")
        self.battery_warning_text.setText(
            "Đang xác nhận pin nguy hại. Vui lòng giữ pin trong khay."
        )
        self.hazardous_battery_confirmation_requested.emit()

    def set_hazardous_confirmation_result(self, ok: bool, message: str) -> None:
        if ok:
            self._battery_confirmation_pending = True
            self.btn_confirm_battery.setEnabled(False)
            self.btn_confirm_battery.setText("Đã xác nhận - đang đổ...")
            self.battery_warning_text.setText(
                "Đã xác nhận pin nguy hại. Hệ thống đang gửi pin vào Vô cơ."
            )
            return
        self._battery_confirmation_pending = False
        self.btn_confirm_battery.setText("Thử xác nhận lại")
        self.battery_warning_text.setText(str(message or "Không thể xác nhận pin."))
        self.btn_confirm_battery.setEnabled(
            bool(self.battery_warning.isVisible() and self._actuation_test_mode and self._uart_ok)
        )

    def set_speaker_output_mode(self, mode: str, emit: bool = False) -> None:
        normalized = "computer_speaker" if str(mode or "").strip() == "computer_speaker" else "hardware"
        self._speaker_output_mode = normalized
        self.btn_hw_speaker.blockSignals(True)
        self.btn_pc_speaker.blockSignals(True)
        self.btn_hw_speaker.setChecked(normalized == "hardware")
        self.btn_pc_speaker.setChecked(normalized == "computer_speaker")
        self.btn_hw_speaker.blockSignals(False)
        self.btn_pc_speaker.blockSignals(False)
        self._refresh_speaker_status()
        if emit:
            self.speaker_output_mode_changed.emit(normalized)

    def set_speaker_voice_gender(self, gender: str) -> None:
        self._speaker_voice_gender = normalize_voice_gender(gender)
        self._refresh_speaker_status()

    def _refresh_speaker_status(self) -> None:
        text = self._speaker_status_text()
        self.speaker_status.setText(text)
        self.speaker_status.setVisible(bool(text))

    def _speaker_status_text(self) -> str:
        status = voice_pack_status(self._speaker_voice_gender)
        missing = [name for name, ok in status.items() if not ok]
        if self._speaker_output_mode != "computer_speaker" or not missing:
            return ""
        return f"Thiếu {len(missing)} file âm thanh cho loa laptop."

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
            "Dừng tự động" if self._actuation_test_mode else "Bật phân loại tự động"
        )
        self.btn_actuation.setObjectName("danger" if self._actuation_test_mode else "secondary")
        _set_button_icon(self.btn_actuation, "hardware")
        self.btn_actuation.style().unpolish(self.btn_actuation)
        self.btn_actuation.style().polish(self.btn_actuation)
        self.btn_actuation.blockSignals(False)
        self._sync_dispatch_mode_label()
        self.set_hazardous_battery_warning(self.battery_warning.isVisible())
        if emit:
            self.actuation_test_mode_toggled.emit(self._actuation_test_mode)

    def set_dispatch_status(self, status: str) -> None:
        self._dispatch_status = str(status or "").strip()
        self._sync_dispatch_mode_label()

    def set_auto_sort_state(self, state: str) -> None:
        normalized = str(state or "").strip().upper()
        if normalized not in {"READY", "DETECTING", "SORTING", "RETURNING", "WAITING_EMPTY"}:
            normalized = "WAITING_EMPTY"
        self._auto_sort_state = normalized
        self._sync_dispatch_mode_label()

    def _sync_dispatch_mode_label(self) -> None:
        if self._actuation_test_mode:
            if self._uart_ok:
                state_labels = {
                    "READY": "Sẵn sàng",
                    "DETECTING": "Đang nhận diện",
                    "SORTING": "Đang đổ rác",
                    "RETURNING": "Đang về HOME",
                    "WAITING_EMPTY": "Chờ khay trống",
                }
                self.dispatch_mode_label.setText(state_labels[self._auto_sort_state])
                detail = (
                    "Phân loại tự động đang bật; mỗi vật hợp lệ chỉ tạo một lệnh đổ "
                    "và phải lấy khỏi khay trước lượt kế tiếp."
                )
                if self._uart_protocol == "plain_group":
                    detail += " Format: huuco / voco / taiche."
                elif self._uart_protocol == "sort_line":
                    detail += " Format: SORT:<cmd>:<conf>."
            else:
                self.dispatch_mode_label.setText("Chờ UART")
                detail = "Đã bật gửi nhưng chưa thấy Arduino/COM; app chưa gửi được lệnh thật."
            self.dispatch_mode_label.setStyleSheet(
                _dispatch_pill_style(
                    color="#FBBF24",
                    border="rgba(251,191,36,0.42)",
                    background="rgba(251,191,36,0.10)",
                )
            )
        else:
            self.dispatch_mode_label.setText("Chỉ nhận diện")
            detail = "Không gửi lệnh xuống Arduino. Bật tự động sau khi camera, ROI và UART đã sẵn sàng."
            self.dispatch_mode_label.setStyleSheet(
                _dispatch_pill_style(
                    color="#67E8F9",
                    border="rgba(103,232,249,0.32)",
                    background="rgba(103,232,249,0.08)",
                )
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

    def update_frame(self, frame, detections: list[Detection], roi=None) -> None:
        if self._paused or not self._cam_on:
            return
        if not self.isVisible():
            return
        self.video.set_roi(roi)
        self.video.set_frame(frame)
        self.video.set_detections(detections)

    def stabilize_detections(self, detections: list[Detection]) -> list[Detection]:
        return self._display_stabilizer.update(detections)

    def append_detection(self, cls_name: str, conf: float, ts: str, detail: str = "") -> None:
        self.set_current_detections([(cls_name, conf, ts, detail)])

    def set_current_detections(
        self,
        rows: list[tuple[str, float, str, str]],
    ) -> None:
        """Replace per-frame guesses instead of accumulating contradictory labels."""

        self.stream.clear()
        for cls_name, conf, ts, detail in rows[:DETECTION_STREAM_LIMIT]:
            text = self._detection_text(cls_name, conf, ts, detail)
            item = QListWidgetItem(text)
            item.setToolTip(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
            self.stream.addItem(item)

    @staticmethod
    def _detection_text(
        cls_name: str,
        conf: float,
        ts: str,
        detail: str,
    ) -> str:
        suffix = f"\n    {detail}" if detail else ""
        return f"*  {cls_name:<10} {conf:.2f}    {ts}{suffix}"

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
        self.set_hazardous_battery_warning(self.battery_warning.isVisible())

    def set_avg_conf(self, conf: float) -> None:
        self.card_acc.set_value(f"{conf:.2f}")
