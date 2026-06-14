# Auto Sort And Home Return Fix

## Context

Desktop auto sort recognized a valid object but remained at `waiting empty tray`.
The two-servo tray could also return slightly off-center after a dump.

## What Happened

- Auto-sort reset always disarmed the dispatch guard, including the moment the
  operator enabled automatic sorting with an object already on the tray.
- The firmware returned D6 and D7 together. Under load this could twist the
  linkage before both servos reached HOME.
- Deferred proximity audio ran before `ACK`, consuming most of the 4500 ms UART
  timeout budget.

## Decisions

- Arm only the first object immediately when automatic sorting is enabled.
- Keep ACK, busy, stable-frame, single-object, ROI, and empty-tray re-arm gates.
- Remove the redundant global cooldown; empty-tray re-arm remains mandatory
  after each completed dispatch.
- Return D7 to the level position before centering D6, then hold exact HOME.
- Publish `ACK` immediately after HOME and play queued proximity audio afterward.

## Verification

- Focused and blast-radius tests: `105 passed`.
- Ruff: passed.
- Arduino Uno firmware: compiled and uploaded to `COM8`.
- Hardware silent cycles: `I`, `O`, and `R` all returned matching ACK; stable
  cycles completed in about 3.1 to 3.9 seconds.

## Unresolved Questions

- Physical centering still requires operator observation because software has
  no tray-position sensor.
