"""UART wire protocol encoders and parsers (pure functions)."""
from __future__ import annotations


def encode_sort(command: str, conf: float) -> bytes:
    if not command or len(command) != 1:
        raise ValueError("command must be exactly 1 character")
    conf = max(0.0, min(1.0, float(conf)))
    return f"SORT:{command}:{conf:.2f}\n".encode("utf-8")


def encode_ping() -> bytes:
    return b"PING\n"


def parse_line(raw: bytes):
    try:
        s = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    if not s:
        return None
    if s == "PONG":
        return ("pong", None, None)
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
    return None
