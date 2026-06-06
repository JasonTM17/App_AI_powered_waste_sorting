from app.utils.serial_enum import (
    eligible_usb_serial_ports,
    is_eligible_usb_serial_port,
    select_single_usb_serial_port,
)


def test_select_single_usb_serial_port_picks_only_usb_ch340():
    ports = [
        {"device": "COM3", "name": "Bluetooth", "hwid": "BTHENUM", "is_usb": False},
        {"device": "COM8", "name": "USB-SERIAL CH340", "hwid": "USB VID:1A86", "is_usb": True},
    ]

    result = select_single_usb_serial_port(ports)

    assert result.selected is True
    assert result.port == "COM8"


def test_select_single_usb_serial_port_does_not_pick_bluetooth_or_plain_com():
    ports = [
        {"device": "COM3", "name": "Standard Serial over Bluetooth", "hwid": "BTHENUM", "is_usb": True},
        {"device": "COM4", "name": "COM Port", "hwid": "ACPI", "is_usb": False},
    ]

    assert eligible_usb_serial_ports(ports) == []
    assert select_single_usb_serial_port(ports).selected is False


def test_select_single_usb_serial_port_requires_exactly_one_candidate():
    ports = [
        {"device": "COM8", "name": "USB-SERIAL CH340", "hwid": "USB VID:1A86", "is_usb": True},
        {"device": "COM9", "name": "Arduino Uno", "hwid": "USB VID:2341", "is_usb": True},
    ]

    result = select_single_usb_serial_port(ports)

    assert result.selected is False
    assert result.eligible_count == 2
    assert is_eligible_usb_serial_port(ports[0]) is True
