"""Desktop admin login helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from app.agent.auth_service import AuthIdentity, AuthService, InactiveAccountError


@dataclass(frozen=True)
class DesktopAuthResult:
    ok: bool
    message: str
    token: str = ""
    identity: AuthIdentity | None = None


AuthServiceFactory = Callable[[], AuthService]


def authenticate_desktop_admin(
    username: str,
    password: str,
    *,
    service_factory: AuthServiceFactory = AuthService,
    require_shared_database: bool = False,
) -> DesktopAuthResult:
    clean_username = str(username or "").strip()
    if not clean_username or not password:
        return DesktopAuthResult(False, "Nhập tài khoản và mật khẩu Admin.")
    try:
        service = service_factory()
    except Exception as exc:
        return DesktopAuthResult(False, f"Không mở được hệ thống tài khoản: {exc}")
    if require_shared_database and not str(getattr(service, "database_url", "") or "").strip():
        return DesktopAuthResult(
            False,
            "Desktop app đang yêu cầu dùng SQL auth chung nhưng chưa cấu hình "
            "TRASH_SORTER_AUTH_DATABASE_URL. Hãy đặt Supabase Postgres URL trong .env.local "
            "hoặc Windows env rồi mở lại app.",
        )

    started = perf_counter()
    try:
        result = service.login(clean_username, password, client_label="desktop-admin")
    except InactiveAccountError:
        _log_login_timing(started, clean_username, "inactive")
        return DesktopAuthResult(False, "Tài khoản này đang bị khóa.")
    except SQLAlchemyError as exc:
        _log_login_timing(started, clean_username, "database_error")
        return DesktopAuthResult(
            False,
            "Không đọc được DB tài khoản chung. Kiểm tra Supabase/PostgreSQL "
            f"và khởi động lại app. Chi tiết: {exc.__class__.__name__}",
        )
    except Exception as exc:
        _log_login_timing(started, clean_username, "error")
        return DesktopAuthResult(False, f"Đăng nhập thất bại: {exc}")
    if result is None:
        _log_login_timing(started, clean_username, "invalid")
        message = "Sai tài khoản hoặc mật khẩu."
        if str(getattr(service, "database_url", "") or "").strip():
            message = (
                "PostgreSQL đã kết nối, nhưng tài khoản hoặc mật khẩu Admin không khớp. "
                "Hãy dùng mật khẩu tài khoản trong hệ thống, không dùng mật khẩu kết nối DB."
            )
        return DesktopAuthResult(False, message)
    if result.identity.role != "admin":
        service.revoke_session(result.token)
        _log_login_timing(started, clean_username, "non_admin")
        return DesktopAuthResult(False, "Desktop app chỉ cho phép tài khoản Admin.")
    _log_login_timing(started, clean_username, "ok")
    return DesktopAuthResult(True, "Đăng nhập Admin thành công.", result.token, result.identity)


def _log_login_timing(started: float, username: str, outcome: str) -> None:
    elapsed_ms = int((perf_counter() - started) * 1000)
    logger.info(
        "desktop_login_timing username={} outcome={} elapsed_ms={}",
        username[:64],
        outcome,
        elapsed_ms,
    )
