"""Enumerate serial ports available on the host."""

from __future__ import annotations


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


__all__ = ["list_serial_ports"]
