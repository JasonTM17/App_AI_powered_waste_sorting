"""Presentation helpers for Live detection status text."""

from __future__ import annotations

from app.core.config import normalize_multi_class_warning_text

MULTI_OBJECT_DISPATCH_STATUS = "multiple waste types"
TEST_OFF_ACK_TEXT = "TEST OFF, không gửi xuống phần cứng"
UART_OFF_ACK_TEXT = "UART OFF, không gửi xuống phần cứng"


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
    if dispatch_status:
        return dispatch_status
    return "pending" if uart_connected else UART_OFF_ACK_TEXT


__all__ = [
    "MULTI_OBJECT_DISPATCH_STATUS",
    "TEST_OFF_ACK_TEXT",
    "UART_OFF_ACK_TEXT",
    "live_ack_status_text",
    "multi_object_warning_text",
]
