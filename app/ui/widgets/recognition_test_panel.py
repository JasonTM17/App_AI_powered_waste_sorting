"""Guided controls for repeatable real-waste recognition sessions."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.waste_categories import TRAINING_CLASS_ORDER_45, canonical_class_name


class RecognitionTestPanel(QFrame):
    start_requested = Signal(object)
    pause_requested = Signal()
    resume_requested = Signal()
    abort_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._paused = False

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(10)
        title = QLabel("KIỂM THỬ RÁC THẬT")
        title.setObjectName("mono")
        root.addWidget(title)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        self.sample_name = QLineEdit()
        self.sample_name.setPlaceholderText("Tên mẫu, ví dụ: lon bia đang dùng")
        self.expected_class = QComboBox()
        self.expected_class.setEditable(True)
        self.expected_class.addItems(TRAINING_CLASS_ORDER_45)
        self.btn_add = QPushButton("Thêm mẫu")
        self.btn_add.setObjectName("secondary")
        self.btn_add.clicked.connect(self._add_sample)
        form.addWidget(QLabel("Mẫu thật"), 0, 0)
        form.addWidget(self.sample_name, 0, 1)
        form.addWidget(QLabel("Nhãn thật"), 0, 2)
        form.addWidget(self.expected_class, 0, 3)
        form.addWidget(self.btn_add, 0, 4)

        self.phase = QComboBox()
        self.phase.addItem("Vòng 1 - chỉ nhận diện", "recognition")
        self.phase.addItem("Vòng 2 - servo + ACK/HOME", "servo")
        self.phase.currentIndexChanged.connect(self._sync_phase_defaults)
        self.repetitions = QSpinBox()
        self.repetitions.setRange(1, 20)
        self.repetitions.setValue(5)
        self.countdown = QSpinBox()
        self.countdown.setRange(0, 30)
        self.countdown.setValue(3)
        self.timeout = QSpinBox()
        self.timeout.setRange(1, 60)
        self.timeout.setValue(8)
        form.addWidget(QLabel("Chế độ"), 1, 0)
        form.addWidget(self.phase, 1, 1)
        form.addWidget(QLabel("Lượt/mẫu"), 1, 2)
        form.addWidget(self.repetitions, 1, 3)
        form.addWidget(QLabel("Đếm ngược / timeout"), 2, 0)
        timing = QHBoxLayout()
        timing.addWidget(self.countdown)
        timing.addWidget(QLabel("giây /"))
        timing.addWidget(self.timeout)
        timing.addWidget(QLabel("giây"))
        timing.addStretch()
        form.addLayout(timing, 2, 1, 1, 3)
        root.addLayout(form)

        sample_row = QHBoxLayout()
        self.samples = QListWidget()
        self.samples.setMaximumHeight(92)
        sample_row.addWidget(self.samples, 1)
        self.btn_remove = QPushButton("Xóa mẫu")
        self.btn_remove.setObjectName("secondary")
        self.btn_remove.clicked.connect(self._remove_sample)
        sample_row.addWidget(self.btn_remove)
        root.addLayout(sample_row)

        actions = QHBoxLayout()
        self.btn_start = QPushButton("Bắt đầu phiên")
        self.btn_start.setObjectName("primary")
        self.btn_start.clicked.connect(self._start)
        self.btn_pause = QPushButton("Tạm dừng")
        self.btn_pause.setObjectName("secondary")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._toggle_pause)
        self.btn_abort = QPushButton("Hủy phiên")
        self.btn_abort.setObjectName("danger")
        self.btn_abort.setEnabled(False)
        self.btn_abort.clicked.connect(self.abort_requested.emit)
        actions.addWidget(self.btn_start)
        actions.addWidget(self.btn_pause)
        actions.addWidget(self.btn_abort)
        actions.addStretch()
        root.addLayout(actions)

        result_row = QHBoxLayout()
        status_box = QVBoxLayout()
        self.state_label = QLabel("Chưa chạy")
        self.state_label.setObjectName("h2")
        self.progress_label = QLabel("Đặt khay trống để bắt đầu.")
        self.progress_label.setWordWrap(True)
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        status_box.addWidget(self.state_label)
        status_box.addWidget(self.progress_label)
        status_box.addWidget(self.result_label)
        result_row.addLayout(status_box, 1)
        self.preview = QLabel("Chưa có ảnh")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(220, 124)
        self.preview.setStyleSheet(
            "background:#060E20; border:1px solid #243044; border-radius:8px;"
        )
        result_row.addWidget(self.preview)
        root.addLayout(result_row)

    def set_state(self, payload: object) -> None:
        state = payload if isinstance(payload, dict) else {}
        name = str(state.get("state", "IDLE"))
        labels = {
            "IDLE": "Chưa chạy",
            "WAITING_EMPTY": "Chờ khay trống",
            "COUNTDOWN": "Chuẩn bị đặt vật",
            "SCANNING": "Đang quét",
            "SAVING": "Đang lưu ảnh",
            "WAITING_ACK": "Chờ ACK và HOME",
            "BEEP": "Đã hoàn tất - nghe tiếng bíp",
            "PAUSED": "Đã tạm dừng",
            "COMPLETED": "Hoàn tất phiên",
            "ABORTED": "Đã hủy phiên",
        }
        self.state_label.setText(labels.get(name, name))
        sample = str(state.get("sample_label", "") or "")
        trial = int(state.get("trial_number", 0) or 0)
        total = int(state.get("repetitions", 0) or 0)
        remaining = state.get("remaining_seconds")
        detail = f"Mẫu: {sample} | lượt {trial}/{total}" if sample else ""
        if remaining is not None:
            detail += f" | còn {float(remaining):.1f} giây"
        self.progress_label.setText(detail or labels.get(name, name))
        active = bool(state.get("active"))
        self.btn_start.setEnabled(not active)
        self.btn_pause.setEnabled(active and name != "WAITING_ACK")
        self.btn_abort.setEnabled(active and name != "WAITING_ACK")
        if name != "PAUSED":
            self._paused = False
            self.btn_pause.setText("Tạm dừng")

    def set_trial(self, payload: object) -> None:
        trial = payload if isinstance(payload, dict) else {}
        expected = str(trial.get("expected_class", "-"))
        predicted = str(trial.get("predicted_class") or "không nhận diện")
        verdict = str(trial.get("verdict", "-"))
        confidence = trial.get("confidence")
        confidence_text = (
            f"{float(confidence):.2f}" if confidence is not None else "-"
        )
        self.result_label.setText(
            f"Kết quả: {verdict} | thật: {expected} | AI: {predicted} | "
            f"confidence: {confidence_text}"
        )
        image_path = Path(str(trial.get("annotated_image_path", "") or ""))
        if image_path.exists():
            pixmap = QPixmap(str(image_path))
            self.preview.setPixmap(
                pixmap.scaled(
                    self.preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def set_action_result(self, ok: bool, message: str) -> None:
        color = "#34D399" if ok else "#F87171"
        self.result_label.setStyleSheet(f"color:{color};")
        self.result_label.setText(message)

    def _add_sample(self) -> None:
        typed = self.expected_class.currentText().strip()
        expected = canonical_class_name(typed) or typed
        if expected not in TRAINING_CLASS_ORDER_45:
            self.set_action_result(False, f"Nhãn không hợp lệ: {typed}")
            return
        label = self.sample_name.text().strip() or expected
        item = QListWidgetItem(f"{label} → {expected}")
        item.setData(
            Qt.ItemDataRole.UserRole,
            {"label": label, "expected_class": expected},
        )
        self.samples.addItem(item)
        self.sample_name.clear()

    def _remove_sample(self) -> None:
        row = self.samples.currentRow()
        if row >= 0:
            self.samples.takeItem(row)

    def _start(self) -> None:
        samples = [
            self.samples.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.samples.count())
        ]
        self.start_requested.emit(
            {
                "samples": samples,
                "phase": self.phase.currentData(),
                "repetitions": self.repetitions.value(),
                "countdown_seconds": self.countdown.value(),
                "scan_timeout_seconds": self.timeout.value(),
                "stable_frames": 3,
                "empty_seconds": 2.0,
                "empty_frames": 10,
            }
        )

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self.btn_pause.setText("Tiếp tục" if self._paused else "Tạm dừng")
        if self._paused:
            self.pause_requested.emit()
        else:
            self.resume_requested.emit()

    def _sync_phase_defaults(self) -> None:
        self.repetitions.setValue(
            1 if self.phase.currentData() == "servo" else 5
        )
