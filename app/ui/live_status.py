"""Presentation helpers for Live detection status text."""

from __future__ import annotations

from app.core.config import normalize_multi_class_warning_text

MULTI_OBJECT_DISPATCH_STATUS = "multiple waste types"
WAITING_EMPTY_ACK_TEXT = "Lấy vật ra khỏi khay để nhận lượt tiếp theo."
TEST_OFF_ACK_TEXT = "TEST OFF, không gửi lệnh xuống phần cứng."
UART_OFF_ACK_TEXT = "UART OFF, không gửi lệnh xuống phần cứng."

WAITING_DISPATCH_ACK_TEXT = "Chờ hệ thống gửi lệnh phân loại."

_DISPATCH_STATUS_TEXT = {
    "camera blurry": "Camera bị mờ, không gửi lệnh. Đưa vật ra xa ống kính và lấy nét lại.",
    "camera frame invalid": "Khung hình camera không hợp lệ, không gửi lệnh.",
    "object framing invalid": (
        "Khung vật thể không hợp lệ, không gửi lệnh. Đặt một vật gọn trong vùng nhận diện."
    ),
}


def multi_object_warning_text(dispatch_status: str, warning_text: str) -> str:
    if str(dispatch_status or "").strip().startswith(MULTI_OBJECT_DISPATCH_STATUS):
        return normalize_multi_class_warning_text(warning_text)
    return ""


def live_ack_status_text(
    *,
    test_mode_enabled: bool,
    dispatch_status: str,
    uart_connected: bool,
    multi_class_warning_text: str,
) -> str:
    warning = multi_object_warning_text(dispatch_status, multi_class_warning_text)
    if warning:
        return warning
    if not test_mode_enabled:
        return TEST_OFF_ACK_TEXT
    if str(dispatch_status or "").strip() == "waiting empty tray":
        return WAITING_EMPTY_ACK_TEXT
    if dispatch_status:
        return _DISPATCH_STATUS_TEXT.get(str(dispatch_status).strip(), dispatch_status)
    return WAITING_DISPATCH_ACK_TEXT if uart_connected else UART_OFF_ACK_TEXT


__all__ = [
    "MULTI_OBJECT_DISPATCH_STATUS",
    "TEST_OFF_ACK_TEXT",
    "UART_OFF_ACK_TEXT",
    "WAITING_DISPATCH_ACK_TEXT",
    "WAITING_EMPTY_ACK_TEXT",
    "live_ack_status_text",
    "multi_object_warning_text",
]
