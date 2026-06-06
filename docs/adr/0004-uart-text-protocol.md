# 4. UART text-line protocol over binary

Date: 2026-05-21

## Status

Accepted

## Context

App ↔ Arduino exchange one of: detection sort command, ack, ping, log. Need a wire format.

## Decision

Use newline-terminated UTF-8 text lines:
- App → board, default block mode: `O -> huuco\n`, `R -> voco\n`, `I -> taiche\n`
- App → board, firmware mode: `SORT:<cmd>:<conf>\n`, `PING\n`
- Board → app: `ACK:<cmd>\n`, `NACK:<cmd>:<reason>\n`, `BIN:<bin_index>:<percent>\n`, `PONG\n`, `LOG:<text>\n`

Current 3-bin command mapping:

| Cmd | Bin | Waste group |
|---|---:|---|
| `O` | 1 | Hữu cơ |
| `R` | 2 | Vô cơ |
| `I` | 3 | Tái chế |

The YOLO model can still detect 42 detailed classes. Before hardware dispatch, the app normalizes every detected class to one of the three commands above. Unknown or disabled mappings must not be sent to UART. The default `plain_group` mode targets the visual block firmware that compares strings `huuco`, `voco`, and `taiche`; command meaning stays aligned end-to-end, so app `R` sends `voco\n` and expects `ACK:R`, while app `I` sends `taiche\n` and expects `ACK:I`. `sort_line` is retained for Arduino code that sends ACK/PONG using the same command code it received.

HC-SR04 bin fullness telemetry uses `BIN:<bin_index>:<percent>`, where `bin_index` is `1..3` and `percent` is `0..100`. The agent treats readings as stale after 10 seconds without a new value.

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
