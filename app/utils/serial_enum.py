"""Enumerate and select serial ports available on the host."""

from __future__ import annotations

from dataclasses import dataclass

BLOCKED_SERIAL_HINTS = ("BLUETOOTH", "BTHENUM")


@dataclass(frozen=True)
class UartAutoSelectResult:
    port: str = ""
    message: str = ""
    eligible_count: int = 0

    @property
    def selected(self) -> bool:
        return bool(self.port)


def list_serial_ports() -> list[dict]:
    """Return [{device, name, hwid, is_usb}] for every visible COM port.

    Uses pyserial's list_ports which already abstracts the OS. On Windows
    each entry's hwid contains the VID/PID, so we flag USB-CDC adapters
    (Arduino, ESP32, FTDI, CH340, etc.) for highlighting in the UI.
    """
    try:
        from serial.tools import list_ports
    except Exception:
        return []
    out = []
    for p in list_ports.comports():
        hwid = (p.hwid or "").upper()
        out.append(
            {
                "device": p.device,
                "name": p.description or p.device,
                "hwid": p.hwid or "",
                "is_usb": "USB" in hwid or "VID:" in hwid,
            }
        )
    out.sort(key=lambda x: (not x["is_usb"], x["device"]))
    return out


def is_eligible_usb_serial_port(port: dict) -> bool:
    if not port.get("is_usb"):
        return False
    text = " ".join(str(port.get(key, "")) for key in ("device", "name", "hwid")).upper()
    return not any(hint in text for hint in BLOCKED_SERIAL_HINTS)


def eligible_usb_serial_ports(ports: list[dict]) -> list[dict]:
    rows = [p for p in ports if is_eligible_usb_serial_port(p)]
    rows.sort(key=lambda p: str(p.get("device", "")))
    return rows


def select_single_usb_serial_port(ports: list[dict]) -> UartAutoSelectResult:
    eligible = eligible_usb_serial_ports(ports)
    if len(eligible) == 1:
        port = str(eligible[0].get("device") or "").strip()
        return UartAutoSelectResult(
            port=port,
            message=f"Auto-selected USB/Arduino UART port {port}",
            eligible_count=1,
        )
    if not eligible:
        return UartAutoSelectResult(
            message="UART OFF, khong gui xuong phan cung: chua thay cong USB/Arduino.",
            eligible_count=0,
        )
    names = ", ".join(str(p.get("device") or "") for p in eligible)
    return UartAutoSelectResult(
        message=(
            "Co nhieu cong USB/Arduino "
            f"({names}); vui long chon thu cong truoc khi gui xuong phan cung."
        ),
        eligible_count=len(eligible),
    )


__all__ = [
    "UartAutoSelectResult",
    "eligible_usb_serial_ports",
    "is_eligible_usb_serial_port",
    "list_serial_ports",
    "select_single_usb_serial_port",
]
