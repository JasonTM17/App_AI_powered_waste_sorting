"""Dedicated page for guided real-waste recognition QA sessions."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.ui.widgets.recognition_test_panel import RecognitionTestPanel


class RecognitionTestPage(QWidget):
    recognition_test_start_requested = Signal(object)
    recognition_test_pause_requested = Signal()
    recognition_test_resume_requested = Signal()
    recognition_test_abort_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(16)

        title = QLabel("Kiểm thử rác thật")
        title.setObjectName("h1")
        root.addWidget(title)

        description = QLabel(
            "Chạy phiên QA có hướng dẫn cho rác thật trên bệ. Trang này lưu ảnh, "
            "kết quả nhận diện, trạng thái guard và bằng chứng phần cứng riêng khỏi "
            "thống kê vận hành."
        )
        description.setObjectName("muted")
        description.setWordWrap(True)
        root.addWidget(description)

        self.recognition_test_panel = RecognitionTestPanel()
        self.recognition_test_panel.start_requested.connect(
            self.recognition_test_start_requested.emit
        )
        self.recognition_test_panel.pause_requested.connect(
            self.recognition_test_pause_requested.emit
        )
        self.recognition_test_panel.resume_requested.connect(
            self.recognition_test_resume_requested.emit
        )
        self.recognition_test_panel.abort_requested.connect(
            self.recognition_test_abort_requested.emit
        )
        root.addWidget(self.recognition_test_panel)
        root.addStretch()

    def set_recognition_test_state(self, payload: object) -> None:
        self.recognition_test_panel.set_state(payload)

    def set_recognition_test_trial(self, payload: object) -> None:
        self.recognition_test_panel.set_trial(payload)

    def set_recognition_test_action_result(self, ok: bool, message: str) -> None:
        self.recognition_test_panel.set_action_result(ok, message)
