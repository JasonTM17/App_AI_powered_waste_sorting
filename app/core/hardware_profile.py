"""Fixed hardware wiring profile for the real block-diagram sorter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HardwareCommand = Literal["O", "R", "I"]


@dataclass(frozen=True)
class HardwareRoute:
    command: HardwareCommand
    label: str
    serial_payload: str
    bin_index: int
    servo_pin: str
    servo_positions: dict[str, int]
    gd5800_track: int

    @property
    def payload_line(self) -> str:
        return f"{self.serial_payload}\\n"


@dataclass(frozen=True)
class BinSensorPins:
    bin_index: int
    trig_pin: str
    echo_pin: str


@dataclass(frozen=True)
class ProximitySensorPins:
    command: HardwareCommand
    label: str
    pin: str
    active_level: int
    gd5800_track: int
    action: Literal["audio_only"] = "audio_only"
    controls_servo: bool = False


PROFILE_ID = "LEGACY_2_SERVO_OPENSMART"
PROFILE_NAME = "Block diagram: two-servo gate plus OPEN-SMART Serial MP3 Player A"
AUDIO_PROTOCOL = "open_smart_serial_mp3_a"
SERVO_WAIT_POSITIONS = {"D6": 90, "D7": 85}
HOME_CALIBRATION_CANDIDATES: tuple[dict[str, object], ...] = (
    {"label": "Home current", "D6": 90, "D7": 85},
    {"label": "Home D7 -2", "D6": 90, "D7": 83},
    {"label": "Home D7 +2", "D6": 90, "D7": 87},
    {"label": "Home D6 -2", "D6": 88, "D7": 85},
    {"label": "Home D6 +2", "D6": 92, "D7": 85},
)
INORGANIC_REPLAY_CANDIDATES: tuple[dict[str, object], ...] = (
    {"label": "Vo co current", "command": "R", "D6": 90, "D7": 0},
    {"label": "Vo co previous", "command": "R", "D6": 145, "D7": 180},
    {"label": "Vo co max max", "command": "R", "D6": 180, "D7": 180},
    {"label": "Vo co D6 min", "command": "R", "D6": 0, "D7": 180},
    {"label": "Vo co D7 min", "command": "R", "D6": 180, "D7": 0},
    {"label": "Vo co both min", "command": "R", "D6": 0, "D7": 0},
    {"label": "Vo co D6 45", "command": "R", "D6": 45, "D7": 180},
    {"label": "Vo co D7 45", "command": "R", "D6": 180, "D7": 45},
)
ROUTES: tuple[HardwareRoute, ...] = (
    HardwareRoute("O", "Huu co", "huuco", 1, "D6/D7", {"D6": 90, "D7": 180}, 2),
    HardwareRoute("R", "Vo co", "voco", 2, "D6/D7", {"D6": 90, "D7": 0}, 4),
    HardwareRoute("I", "Tai che", "taiche", 3, "D6/D7", {"D6": 145, "D7": 180}, 3),
)

SENSOR_PINS: tuple[BinSensorPins, ...] = ()

PROXIMITY_SENSORS: tuple[ProximitySensorPins, ...] = (
    ProximitySensorPins("O", "Huu co", "D10", 0, 5),
    ProximitySensorPins("I", "Tai che", "D11", 0, 6),
    ProximitySensorPins("R", "Vo co", "D12", 0, 7),
)

GD5800_TX_PIN = "D5"
GD5800_RX_PIN = "D4"
GD5800_SERIAL_MODE = "REVERSE_RX_D4_TX_D5"
GD5800_STARTUP_TRACK = 1
MP3_VOLUME_DEFAULT = 30
DEFAULT_BAUD = 9600
DEFAULT_PROTOCOL = "plain_group"
HOME_DEGREES = SERVO_WAIT_POSITIONS
DUMP_DEGREES = "per_route"
HOLD_MS = 2000
PRE_SORT_HOME_SETTLE_MS = 0
RETURN_SETTLE_MS = 1500
SERVO_IDLE_POLICY = "detach"

_ROUTES_BY_COMMAND: dict[str, HardwareRoute] = {route.command: route for route in ROUTES}


def route_for_command(command: str) -> HardwareRoute | None:
    return _ROUTES_BY_COMMAND.get(command.strip().upper())


def hardware_profile_payload() -> dict[str, object]:
    return {
        "profile_id": PROFILE_ID,
        "profile_name": PROFILE_NAME,
        "audio_protocol": AUDIO_PROTOCOL,
        "baud": DEFAULT_BAUD,
        "protocol": DEFAULT_PROTOCOL,
        "servo": {
            "mode": "two_servo_gate",
            "wait_degrees": SERVO_WAIT_POSITIONS,
            "dump_degrees": DUMP_DEGREES,
            "hold_ms": HOLD_MS,
            "pre_sort_home_settle_ms": PRE_SORT_HOME_SETTLE_MS,
            "return_settle_ms": RETURN_SETTLE_MS,
            "idle_policy": SERVO_IDLE_POLICY,
        },
        "calibration": {
            "home_candidates": list(HOME_CALIBRATION_CANDIDATES),
            "inorganic_replay_candidates": list(INORGANIC_REPLAY_CANDIDATES),
            "sensor_audio_only": True,
        },
        "gd5800": {
            "module": "OPEN-SMART Serial MP3 Player A",
            "audio_protocol": AUDIO_PROTOCOL,
            "serial_mode": GD5800_SERIAL_MODE,
            "tx_pin": GD5800_TX_PIN,
            "rx_pin": GD5800_RX_PIN,
            "startup_track": GD5800_STARTUP_TRACK,
            "volume_default": MP3_VOLUME_DEFAULT,
            "select_tf_frame": "7E 03 35 01 EF",
            "play_index_frame": "7E 04 41 00 <track> EF",
        },
        "routes": [
            {
                "command": route.command,
                "label": route.label,
                "serial_payload": route.serial_payload,
                "payload_line": route.payload_line,
                "bin_index": route.bin_index,
                "servo_pin": route.servo_pin,
                "servo_positions": route.servo_positions,
                "gd5800_track": route.gd5800_track,
            }
            for route in ROUTES
        ],
        "bin_sensors": [
            {
                "bin_index": pins.bin_index,
                "trig_pin": pins.trig_pin,
                "echo_pin": pins.echo_pin,
            }
            for pins in SENSOR_PINS
        ],
        "proximity_sensors": [
            {
                "command": pins.command,
                "label": pins.label,
                "pin": pins.pin,
                "active_level": pins.active_level,
                "gd5800_track": pins.gd5800_track,
                "action": pins.action,
                "controls_servo": pins.controls_servo,
            }
            for pins in PROXIMITY_SENSORS
        ],
    }


__all__ = [
    "AUDIO_PROTOCOL",
    "DEFAULT_BAUD",
    "DEFAULT_PROTOCOL",
    "DUMP_DEGREES",
    "GD5800_RX_PIN",
    "GD5800_SERIAL_MODE",
    "GD5800_STARTUP_TRACK",
    "GD5800_TX_PIN",
    "HOLD_MS",
    "HOME_CALIBRATION_CANDIDATES",
    "HOME_DEGREES",
    "INORGANIC_REPLAY_CANDIDATES",
    "MP3_VOLUME_DEFAULT",
    "PRE_SORT_HOME_SETTLE_MS",
    "PROFILE_ID",
    "PROFILE_NAME",
    "PROXIMITY_SENSORS",
    "RETURN_SETTLE_MS",
    "ROUTES",
    "SENSOR_PINS",
    "SERVO_IDLE_POLICY",
    "HardwareCommand",
    "HardwareRoute",
    "ProximitySensorPins",
    "hardware_profile_payload",
    "route_for_command",
]
