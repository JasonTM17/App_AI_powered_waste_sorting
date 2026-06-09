"""Audio output controls for the Settings page."""

from __future__ import annotations

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config import AppConfig
from app.core.voice_pack import voice_pack_status
from app.utils.paths import resource_path


def _icon(name: str) -> QIcon:
    path = resource_path(f"app/ui/resources/icons/{name}.svg")
    return QIcon(str(path)) if path.exists() else QIcon()


class AudioSettingsSection(QWidget):
    voice_test_requested = Signal(str)

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        selector = QHBoxLayout()
        selector.setSpacing(8)
        self.hardware_button = self._mode_button("Loa phần cứng", "hardware")
        self.computer_button = self._mode_button("Loa laptop", "computer_speaker")
        selector.addWidget(self.hardware_button)
        selector.addWidget(self.computer_button)
        layout.addLayout(selector)

        self.status_label = QLabel(self._voice_status_text())
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        cooldown_row = QHBoxLayout()
        cooldown_row.setSpacing(10)
        cooldown_row.addWidget(QLabel("Cooldown loa PC"))
        self.speaker_cooldown = QDoubleSpinBox()
        self.speaker_cooldown.setRange(0.0, 60.0)
        self.speaker_cooldown.setDecimals(1)
        self.speaker_cooldown.setSingleStep(0.5)
        self.speaker_cooldown.setSuffix(" s")
        self.speaker_cooldown.setValue(float(cfg.speaker.cooldown_seconds))
        cooldown_row.addWidget(self.speaker_cooldown)
        cooldown_row.addStretch()
        layout.addLayout(cooldown_row)

        tests = QGridLayout()
        tests.setHorizontalSpacing(8)
        tests.setVerticalSpacing(8)
        for index, (label, command) in enumerate(
            (
                ("Test hữu cơ", "O"),
                ("Test vô cơ", "R"),
                ("Test tái chế", "I"),
                ("Test cảnh báo", "warning"),
            )
        ):
            button = QPushButton(label)
            button.setObjectName("secondary")
            button.setIcon(_icon("speaker"))
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(
                lambda _checked=False, cmd=command: self.voice_test_requested.emit(cmd)
            )
            tests.addWidget(button, index // 2, index % 2)
        layout.addLayout(tests)

        self.set_output_mode(cfg.speaker.output_mode)
        self._group.idToggled.connect(lambda *_args: self._sync_controls())
        self._sync_controls()

    def _mode_button(self, label: str, mode: str) -> QPushButton:
        button = QPushButton(label)
        button.setCheckable(True)
        button.setObjectName("segmented")
        button.setIcon(_icon("hardware" if mode == "hardware" else "speaker"))
        button.setIconSize(QSize(18, 18))
        self._group.addButton(button, 1 if mode == "computer_speaker" else 0)
        return button

    def output_mode(self) -> str:
        return "computer_speaker" if self.computer_button.isChecked() else "hardware"

    def set_output_mode(self, mode: str) -> None:
        if mode == "computer_speaker":
            self.computer_button.setChecked(True)
        else:
            self.hardware_button.setChecked(True)
        self._sync_controls()

    def _sync_controls(self) -> None:
        self.speaker_cooldown.setEnabled(self.output_mode() == "computer_speaker")

    def _voice_status_text(self) -> str:
        status = voice_pack_status()
        ready = sum(1 for ok in status.values() if ok)
        total = len(status)
        missing = [name for name, ok in status.items() if not ok]
        if not missing:
            return f"Loa laptop sẵn sàng ({ready}/{total} file)."
        return f"Loa laptop thiếu {len(missing)} file: {', '.join(missing)}."
