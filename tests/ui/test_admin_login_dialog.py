from typing import ClassVar

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog, QLineEdit

import app.ui.widgets.admin_login_dialog as login_dialog_module
from app.agent.auth_service import AuthIdentity
from app.ui.desktop_auth import DesktopAuthResult
from app.ui.widgets.admin_login_dialog import AdminLoginDialog


class _FakeLoginWorker(QObject):
    finished_with_result = Signal(object)
    finished = Signal()
    instances: ClassVar[list["_FakeLoginWorker"]] = []

    def __init__(self, username: str, password: str):
        super().__init__()
        self.username = username
        self.password = password
        self.running = False
        self.deleted = False
        self.instances.append(self)

    def start(self) -> None:
        self.running = True

    def isRunning(self) -> bool:  # noqa: N802 - Qt compatibility in fake worker.
        return self.running

    def deleteLater(self) -> None:  # noqa: N802 - Qt compatibility in fake worker.
        self.deleted = True
        super().deleteLater()

    def emit_result(self, result: DesktopAuthResult) -> None:
        self.finished_with_result.emit(result)

    def finish(self) -> None:
        self.running = False
        self.finished.emit()


def test_admin_login_waits_for_worker_finished_before_accepting(qtbot, monkeypatch):
    _FakeLoginWorker.instances = []
    monkeypatch.setattr(login_dialog_module, "_LoginWorker", _FakeLoginWorker)
    dialog = AdminLoginDialog()
    qtbot.addWidget(dialog)

    dialog.username.setText("admin")
    dialog.password.setText("secret-pass-123")
    dialog._submit()
    worker = _FakeLoginWorker.instances[0]

    worker.emit_result(
        DesktopAuthResult(
            True,
            "ok",
            token="token",
            identity=AuthIdentity(
                account_id=1,
                role="admin",
                username="admin",
                expires_at="2026-06-13T00:00:00Z",
            ),
        )
    )

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog._worker is worker

    worker.finish()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog._worker is None
    assert worker.deleted is True


def test_admin_login_password_visibility_toggle(qtbot):
    dialog = AdminLoginDialog()
    qtbot.addWidget(dialog)

    assert dialog.password.echoMode() == QLineEdit.EchoMode.Password
    assert dialog.btn_toggle_password.toolTip() == "Hiện mật khẩu"

    dialog.btn_toggle_password.click()

    assert dialog.password.echoMode() == QLineEdit.EchoMode.Normal
    assert dialog.btn_toggle_password.toolTip() == "Ẩn mật khẩu"

    dialog.btn_toggle_password.click()

    assert dialog.password.echoMode() == QLineEdit.EchoMode.Password
