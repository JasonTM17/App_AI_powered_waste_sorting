"""Admin-only desktop login dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from app.agent.auth_service import AuthIdentity
from app.ui.brand_assets import brand_icon
from app.ui.desktop_auth import DesktopAuthResult, authenticate_desktop_admin


class AdminLoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(brand_icon())
        self.token = ""
        self.identity: AuthIdentity | None = None
        self._worker: _LoginWorker | None = None
        self.setWindowTitle("Đăng nhập Admin")
        self.setModal(True)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(14)

        title = QLabel("Trash Sorter Pro")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        subtitle = QLabel("Đăng nhập bằng tài khoản Admin để vận hành máy phân loại.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        form_box = QFrame()
        form_box.setObjectName("card")
        form = QFormLayout(form_box)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)

        self.username = QLineEdit()
        self.username.setPlaceholderText("admin")
        self.username.returnPressed.connect(self._submit)
        form.addRow("Tài khoản", self.username)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.returnPressed.connect(self._submit)
        form.addRow("Mật khẩu", self.password)
        root.addWidget(form_box)

        self.message = QLabel("")
        self.message.setObjectName("error")
        self.message.setWordWrap(True)
        self.message.setVisible(False)
        root.addWidget(self.message)

        self.btn_login = QPushButton("Đăng nhập")
        self.btn_login.setObjectName("primary")
        self.btn_login.clicked.connect(self._submit)
        root.addWidget(self.btn_login, alignment=Qt.AlignmentFlag.AlignRight)
        self.username.setFocus()

    def _submit(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.message.setVisible(False)
        self.btn_login.setEnabled(False)
        self.btn_login.setText("Đang đăng nhập...")
        self.username.setEnabled(False)
        self.password.setEnabled(False)
        worker = _LoginWorker(
            self.username.text(),
            self.password.text(),
        )
        self._worker = worker
        worker.finished_with_result.connect(self._finish_submit)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _finish_submit(self, result: DesktopAuthResult) -> None:
        self._worker = None
        self.btn_login.setEnabled(True)
        self.btn_login.setText("Đăng nhập")
        self.username.setEnabled(True)
        self.password.setEnabled(True)
        if not result.ok:
            self.message.setText(result.message)
            self.message.setVisible(True)
            return
        self.token = result.token
        self.identity = result.identity
        self.accept()


class _LoginWorker(QThread):
    finished_with_result = Signal(object)

    def __init__(self, username: str, password: str):
        super().__init__()
        self._username = username
        self._password = password

    def run(self) -> None:
        result = authenticate_desktop_admin(
            self._username,
            self._password,
            require_shared_database=True,
        )
        self.finished_with_result.emit(result)
