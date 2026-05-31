from app.core.config import MULTI_CLASS_WARNING_TEXT
from app.ui.live_status import (
    TEST_OFF_ACK_TEXT,
    UART_OFF_ACK_TEXT,
    live_ack_status_text,
    multi_object_warning_text,
)


def test_multi_object_warning_text_accepts_detailed_dispatch_status():
    assert multi_object_warning_text("multiple waste types", "only one") == MULTI_CLASS_WARNING_TEXT
    assert (
        multi_object_warning_text("multiple waste types (2 visible objects)", "only one")
        == MULTI_CLASS_WARNING_TEXT
    )
    assert multi_object_warning_text("TEST OFF", "only one") == ""


def test_live_ack_status_shows_multi_object_warning_even_when_test_mode_off():
    assert (
        live_ack_status_text(
            test_mode_enabled=False,
            dispatch_status="multiple waste types",
            uart_connected=True,
            multi_class_warning_text="only one",
        )
        == MULTI_CLASS_WARNING_TEXT
    )


def test_live_ack_status_keeps_test_off_when_no_multi_object_warning():
    assert (
        live_ack_status_text(
            test_mode_enabled=False,
            dispatch_status="TEST OFF",
            uart_connected=True,
            multi_class_warning_text="only one",
        )
        == TEST_OFF_ACK_TEXT
    )


def test_live_ack_status_reports_uart_off_when_test_mode_on_and_idle():
    assert (
        live_ack_status_text(
            test_mode_enabled=True,
            dispatch_status="",
            uart_connected=False,
            multi_class_warning_text="only one",
        )
        == UART_OFF_ACK_TEXT
    )
