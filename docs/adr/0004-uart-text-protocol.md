# 4. UART text-line protocol over binary

Date: 2026-05-21

## Status

Accepted

## Context

App ↔ Arduino exchange one of: detection sort command, ack, ping, log. Need a wire format.

## Decision

Use newline-terminated UTF-8 text lines:
- App → board: `SORT:<cmd>:<conf>\n`, `PING\n`
- Board → app: `ACK:<cmd>\n`, `NACK:<cmd>:<reason>\n`, `PONG\n`, `LOG:<text>\n`

## Consequences

**Positive:** Debuggable with PuTTY/Arduino Serial Monitor by hand. No checksums needed (rare bit errors at 9600 baud over 1m USB). Trivial parser. New message types backward-compatible.
**Negative:** ~25% larger payload than binary frames. Confidence is a string format, not float bytes.
**Neutral:** Throughput is fine — at 9600 baud we send ≤ 5 commands/sec, far under line rate.

## Alternatives considered

- Binary framing with CRC16 — rejected: overkill for this baud rate and topology, hard to debug.
- JSON lines — rejected: parsing overhead on Arduino, line lengths grow fast.

## References

- `app/core/uart_protocol.py`
- `firmware/arduino_servo/arduino_servo.ino` (planned)
