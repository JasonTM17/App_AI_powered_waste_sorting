"""Admin-only desktop login dialog."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.agent.auth_service import AuthIdentity
from app.ui.brand_assets import brand_icon
from app.ui.desktop_auth import DesktopAuthResult, authenticate_desktop_admin
from app.utils.paths import resource_path


class AdminLoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(brand_icon())
        self.token = ""
        self.identity: AuthIdentity | None = None
        self._worker: _LoginWorker | None = None
        self._accept_after_worker_finished = False
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

        password_row = QWidget()
        password_layout = QHBoxLayout(password_row)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.setSpacing(8)
        password_layout.addWidget(self.password, 1)

        self.btn_toggle_password = QToolButton()
        self.btn_toggle_password.setObjectName("passwordVisibility")
        self.btn_toggle_password.setAccessibleName("Hiện mật khẩu")
        self.btn_toggle_password.setToolTip("Hiện mật khẩu")
        self.btn_toggle_password.setCheckable(True)
        self.btn_toggle_password.setFixedSize(42, 40)
        self.btn_toggle_password.setIconSize(QSize(20, 20))
        self.btn_toggle_password.clicked.connect(self._toggle_password_visibility)
        self._update_password_visibility_icon()
        password_layout.addWidget(self.btn_toggle_password)
        form.addRow("Mật khẩu", password_row)
        root.addWidget(form_box)

        auth_status = QLabel(
            "Xác thực: PostgreSQL. Dùng mật khẩu tài khoản Admin, "
            "không dùng mật khẩu kết nối cơ sở dữ liệu."
        )
        auth_status.setObjectName("muted")
        auth_status.setWordWrap(True)
        root.addWidget(auth_status)

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

    def _toggle_password_visibility(self, visible: bool) -> None:
        echo_mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.password.setEchoMode(echo_mode)
        self._update_password_visibility_icon()

    def _update_password_visibility_icon(self) -> None:
        visible = self.btn_toggle_password.isChecked()
        icon_name = "eye-off.svg" if visible else "eye.svg"
        action = "Ẩn mật khẩu" if visible else "Hiện mật khẩu"
        icon_path = resource_path(f"app/ui/resources/icons/{icon_name}")
        self.btn_toggle_password.setIcon(QIcon(str(icon_path)))
        self.btn_toggle_password.setAccessibleName(action)
        self.btn_toggle_password.setToolTip(action)

    def _submit(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.message.setVisible(False)
        self.btn_login.setEnabled(False)
        self.btn_login.setText("Đang đăng nhập...")
        self.username.setEnabled(False)
        self.password.setEnabled(False)
        self.btn_toggle_password.setEnabled(False)
        self._accept_after_worker_finished = False
        worker = _LoginWorker(
            self.username.text(),
            self.password.text(),
        )
        self._worker = worker
        worker.finished_with_result.connect(self._finish_submit)
        worker.finished.connect(self._finish_worker)
        worker.start()

    def _finish_submit(self, result: DesktopAuthResult) -> None:
        self.btn_login.setEnabled(True)
        self.btn_login.setText("Đăng nhập")
        self.username.setEnabled(True)
        self.password.setEnabled(True)
        self.btn_toggle_password.setEnabled(True)
        if not result.ok:
            self.message.setText(result.message)
            self.message.setVisible(True)
            return
        self.token = result.token
        self.identity = result.identity
        self._accept_after_worker_finished = True
        if self._worker is None or not self._worker.isRunning():
            self._accept_after_worker_finished = False
            self.accept()

    def _finish_worker(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        if self._accept_after_worker_finished:
            self._accept_after_worker_finished = False
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
