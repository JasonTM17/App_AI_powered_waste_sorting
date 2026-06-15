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

INVALID_CREDENTIALS_MESSAGE = (
    "Thông tin đăng nhập không chính xác. Vui lòng kiểm tra và thử lại."
)
AUTH_UNAVAILABLE_MESSAGE = (
    "Dịch vụ xác thực tạm thời không khả dụng. Vui lòng thử lại sau."
)
ACCESS_DENIED_MESSAGE = "Không thể cấp quyền truy cập ứng dụng vận hành."


def authenticate_desktop_admin(
    username: str,
    password: str,
    *,
    service_factory: AuthServiceFactory = AuthService,
    require_shared_database: bool = False,
) -> DesktopAuthResult:
    clean_username = str(username or "").strip()
    if not clean_username or not password:
        return DesktopAuthResult(False, "Vui lòng nhập đầy đủ thông tin đăng nhập.")
    try:
        service = service_factory()
    except Exception as exc:
        logger.exception(
            "desktop authentication service initialization failed type={}",
            exc.__class__.__name__,
        )
        return DesktopAuthResult(False, AUTH_UNAVAILABLE_MESSAGE)
    if require_shared_database and not str(getattr(service, "database_url", "") or "").strip():
        logger.error(
            "desktop authentication unavailable reason=shared_auth_store_not_configured"
        )
        return DesktopAuthResult(False, AUTH_UNAVAILABLE_MESSAGE)

    started = perf_counter()
    try:
        result = service.login(clean_username, password, client_label="desktop-admin")
    except InactiveAccountError:
        _log_login_timing(started, clean_username, "inactive")
        return DesktopAuthResult(False, ACCESS_DENIED_MESSAGE)
    except SQLAlchemyError as exc:
        _log_login_timing(started, clean_username, "database_error")
        logger.exception(
            "desktop authentication data-store error type={}",
            exc.__class__.__name__,
        )
        return DesktopAuthResult(False, AUTH_UNAVAILABLE_MESSAGE)
    except Exception as exc:
        _log_login_timing(started, clean_username, "error")
        logger.exception(
            "desktop authentication unexpected error type={}",
            exc.__class__.__name__,
        )
        return DesktopAuthResult(False, AUTH_UNAVAILABLE_MESSAGE)
    if result is None:
        _log_login_timing(started, clean_username, "invalid")
        return DesktopAuthResult(False, INVALID_CREDENTIALS_MESSAGE)
    if result.identity.role != "admin":
        service.revoke_session(result.token)
        _log_login_timing(started, clean_username, "non_admin")
        return DesktopAuthResult(False, ACCESS_DENIED_MESSAGE)
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


__all__ = [
    "ACCESS_DENIED_MESSAGE",
    "AUTH_UNAVAILABLE_MESSAGE",
    "INVALID_CREDENTIALS_MESSAGE",
    "DesktopAuthResult",
    "authenticate_desktop_admin",
]
