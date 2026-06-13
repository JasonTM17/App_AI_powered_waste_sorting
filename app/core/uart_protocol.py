"""UART wire protocol encoders and parsers (pure functions)."""

from __future__ import annotations

from typing import Literal

UartProtocol = Literal["sort_line", "plain_group"]
Mp3TestCommand = Literal[
    "TF",
    "VOL",
    "PLAY",
    "PLAYVOL",
    "NEXT",
    "ONLINE",
    "STATUS",
    "RESET",
    "MODE_PRIMARY",
    "MODE_REVERSE",
    "MODE_QUERY",
]

PLAIN_GROUP_COMMANDS = {
    "O": "huuco",   # Huu co
    "R": "voco",    # Vo co
    "I": "taiche",  # Tai che
}

PLAIN_GROUP_ACK_COMMANDS = {
    "O": "O",
    "R": "R",
    "I": "I",
}


def encode_sort(
    command: str,
    conf: float,
    protocol: UartProtocol = "sort_line",
    *,
    silent: bool = False,
) -> bytes:
    if not command or len(command) != 1:
        raise ValueError("command must be exactly 1 character")
    command = command.upper()
    if silent:
        if command not in PLAIN_GROUP_COMMANDS:
            raise ValueError("silent sort only supports O/R/I commands")
        return f"SORTSILENT:{command}\n".encode()
    if protocol == "plain_group":
        payload = PLAIN_GROUP_COMMANDS.get(command)
        if payload is None:
            raise ValueError("plain_group only supports O/R/I commands")
        return f"{payload}\n".encode()
    conf = max(0.0, min(1.0, float(conf)))
    return f"SORT:{command}:{conf:.2f}\n".encode()


def expected_ack_command(command: str, protocol: UartProtocol = "sort_line") -> str:
    command = command.strip().upper()
    if protocol == "plain_group":
        return PLAIN_GROUP_ACK_COMMANDS.get(command, command)
    return command


def encode_ping() -> bytes:
    return b"PING\n"


def encode_profile_request() -> bytes:
    return b"PROFILE\n"


def encode_angle_test(d6_angle: int, d7_angle: int) -> bytes:
    if not 0 <= int(d6_angle) <= 180 or not 0 <= int(d7_angle) <= 180:
        raise ValueError("servo angles must be between 0 and 180")
    return f"ANGLE:{int(d6_angle)}:{int(d7_angle)}\n".encode()


def encode_home_test(d6_angle: int, d7_angle: int) -> bytes:
    if not 0 <= int(d6_angle) <= 180 or not 0 <= int(d7_angle) <= 180:
        raise ValueError("servo angles must be between 0 and 180")
    return f"HOME:{int(d6_angle)}:{int(d7_angle)}\n".encode()


def encode_sort_angle_test(command: str, d6_angle: int, d7_angle: int) -> bytes:
    command = command.strip().upper()
    if command not in PLAIN_GROUP_COMMANDS:
        raise ValueError("sort angle test only supports O/R/I commands")
    if not 0 <= int(d6_angle) <= 180 or not 0 <= int(d7_angle) <= 180:
        raise ValueError("servo angles must be between 0 and 180")
    return f"SORTTEST:{command}:{int(d6_angle)}:{int(d7_angle)}\n".encode()


def encode_audio_test(track: int) -> bytes:
    if not 1 <= int(track) <= 8:
        raise ValueError("audio track must be between 1 and 8")
    return f"AUDIO:{int(track)}\n".encode()


def encode_mp3_test(command: str, value: int | None = None) -> bytes:
    command = command.strip().upper()
    if command == "TF":
        return b"MP3:TF\n"
    if command == "NEXT":
        return b"MP3:NEXT\n"
    if command == "ONLINE":
        return b"MP3:ONLINE\n"
    if command == "STATUS":
        return b"MP3:STATUS\n"
    if command == "RESET":
        return b"MP3:RESET\n"
    if command in {"MODE_PRIMARY", "PRIMARY"}:
        return b"MP3:MODE:PRIMARY\n"
    if command in {"MODE_REVERSE", "REVERSE"}:
        return b"MP3:MODE:REVERSE\n"
    if command in {"MODE_QUERY", "MODE"}:
        return b"MP3:MODE?\n"
    if command == "VOL":
        if value is None or not 0 <= int(value) <= 30:
            raise ValueError("mp3 volume must be between 0 and 30")
        return f"MP3:VOL:{int(value)}\n".encode()
    if command == "PLAY":
        if value is None or not 1 <= int(value) <= 255:
            raise ValueError("mp3 play track must be between 1 and 255")
        return f"MP3:PLAY:{int(value)}\n".encode()
    if command == "PLAYVOL":
        if value is None or not 1 <= int(value) <= 255:
            raise ValueError("mp3 play-with-volume track must be between 1 and 255")
        return f"MP3:PLAYVOL:30:{int(value)}\n".encode()
    raise ValueError("unsupported mp3 test command")


def protocol_expects_ack(protocol: UartProtocol) -> bool:
    return protocol in {"plain_group", "sort_line"}


def parse_line(raw: bytes):
    try:
        s = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    if not s:
        return None
    if s == "PONG":
        return ("pong", None, None)
    if s.startswith("PROFILE:"):
        return ("profile", s[8:].strip() or None, None)
    if s.startswith("LOG:"):
        return ("log", None, s[4:])
    if s.startswith("ACK:"):
        return ("ack", s[4:].strip() or None, None)
    if s.startswith("NACK:"):
        rest = s[5:]
        if ":" in rest:
            cmd, reason = rest.split(":", 1)
            return ("nack", cmd, reason)
        return ("nack", rest, None)
    if s.startswith("BIN:"):
        parts = s.split(":")
        if len(parts) != 3:
            return None
        try:
            bin_index = int(parts[1])
            percent = int(parts[2])
        except ValueError:
            return None
        if bin_index < 1 or percent < 0 or percent > 100:
            return None
        return ("bin", bin_index, percent)
    if s.startswith("PROX:"):
        value = s[5:].strip().upper()
        if value in {"O", "R", "I"}:
            return ("proximity", value, None)
        return None
    if s.startswith("AUDIO:"):
        parts = s.split(":")
        if len(parts) != 4:
            return None
        command = parts[1].strip().upper()
        source = parts[3].strip().lower()
        try:
            track = int(parts[2])
        except ValueError:
            return None
        if not command or not source or track < 1 or track > 255:
            return None
        return ("audio", command, {"track": track, "source": source})
    if s.startswith("MP3TX:"):
        frame = s[6:].strip().upper()
        return ("mp3", "tx", frame)
    if s.startswith("MP3RX:"):
        frame = s[6:].strip().upper()
        return ("mp3", "rx", frame)
    if s == "MP3:READY":
        return ("mp3", "ready", None)
    if s.startswith("MP3:ERR:"):
        return ("mp3", "error", s[8:].strip() or None)
    if s.startswith("MP3:PROTO:"):
        return ("mp3", "proto", s[10:].strip() or None)
    if s.startswith("MP3:"):
        parts = s.split(":", 2)
        event = parts[1].strip().lower() if len(parts) > 1 else ""
        detail = parts[2].strip() if len(parts) > 2 else None
        if event:
            return ("mp3", event, detail)
    if s.startswith("SERVO:HOME:"):
        parts = s.split(":")
        if len(parts) != 4:
            return None
        try:
            d6 = int(parts[2])
            d7 = int(parts[3])
        except ValueError:
            return None
        if not 0 <= d6 <= 180 or not 0 <= d7 <= 180:
            return None
        return ("servo", "home", {"D6": d6, "D7": d7})
    return None
