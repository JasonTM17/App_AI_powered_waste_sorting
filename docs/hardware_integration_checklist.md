# Hardware Integration Checklist

This checklist uses the block-diagram wiring the user provided.

## Selected Real Hardware Profile

Profile id: `LEGACY_2_SERVO_OPENSMART`.

| Part | Pin / Behavior |
|---|---|
| Serial | `9600` baud |
| OPEN-SMART Serial MP3 Player A | Detected active mode: Arduino TX `D5` to MP3 RX, Arduino RX `D4` from MP3 TX. Original D4/D5 primary mode remains testable. |
| Servo A | `D6` |
| Servo B | `D7` |
| Proximity Huu co | `D10`, active LOW, track `5` |
| Proximity Tai che | `D11`, active LOW, track `6` |
| Proximity Vo co | `D12`, active LOW, track `7` |

Servo positions:

| State | D6 | D7 |
|---|---:|---:|
| Wait | 90 | 85 |
| Huu co `O` | 90 | 180 |
| Firmware `voco` / app `R` Vo co | 90 | 0 |
| Firmware `taiche` / app `I` Tai che | 145 | 180 |

Sorting audio:

| Group | Cmd | Serial text | Bin | Audio |
|---|---|---|---:|---:|
| Huu co | `O` | `huuco\n` | 1 | track 2 |
| Vo co | `R` | `voco\n` | 2 | track 4 |
| Tai che | `I` | `taiche\n` | 3 | track 3 |

## COM Lock Rules

- Only one process can own the Arduino COM port.
- Close Arduino Serial Monitor before running the app.
- Stop duplicate `run_agent.py` processes before reconnecting UART.
- Do not select Bluetooth COM ports.
- If UI shows `Access is denied`, treat it as COM contention until proven otherwise.

## Firmware Smoke Test

Open Serial Monitor at `9600`, newline:

1. `PING` -> `PONG`.
2. `PROFILE` -> `PROFILE:LEGACY_2_SERVO_OPENSMART` and `MP3:PROTO:open_smart_serial_mp3_a`.
3. `MP3:MODE:REVERSE` -> active mode `REVERSE_RX_D4_TX_D5`.
4. `MP3:ONLINE` -> `MP3RX:*` proving the TF card/board replied.
5. `MP3:TF` -> `MP3TX:7E 03 35 01 EF` and `ACK:MP3:TF`.
6. `MP3:VOL:30` -> `MP3TX:7E 03 31 1E EF` and `ACK:MP3:VOL:30`.
7. `AUDIO:1` through `AUDIO:8` -> `MP3TX:7E 04 41 00 <track> EF`, `ACK:AUDIO:<track>`, and real sound from the red board.
8. `huuco` -> track 2, D6=90/D7=180, hold 1800ms, smooth return, `ACK:O`.
9. `taiche` -> track 3, D6=145/D7=180, hold 1800ms, smooth return, `ACK:I`.
10. `voco` -> track 4, D6=90/D7=0, hold 1800ms, smooth return, `ACK:R`.
11. `HOME:90:85`, `HOME:90:83`, `HOME:90:87`, `HOME:88:85`, `HOME:92:85` -> choose the upright tray candidate.
12. `SORTTEST:R:90:0`, `145:180`, `180:180`, `0:180`, `180:0`, `0:0`, `45:180`, `180:45` -> choose the Vo co direction that fully dumps toward the indicated bin.
13. Trigger D10/D11/D12 sensors and confirm `PROX:O/I/R` plus tracks 5/6/7 without servo movement.

Close Serial Monitor before app tests.

2026-06-05 post-flash evidence from COM8:

- Firmware uploaded with `arduino-cli upload -p COM8 --fqbn arduino:avr:uno`.
- `AUDIO:3` returned `ACK:AUDIO:3` and emitted MP3 track 3.
- `AUDIO:4` returned `ACK:AUDIO:4` and emitted MP3 track 4.
- `voco` via app command `R` returned `ACK:R` and emitted `AUDIO:R:4:sort`.
- `taiche` via app command `I` returned `ACK:I` and emitted
  `AUDIO:I:3:sort`.

2026-06-13 post-flash evidence from COM8:

- Current firmware compiled and uploaded as `arduino:avr:uno`.
- Hardware audio-only tracks `2`, `4`, `3`, and warning track `8` returned
  `MP3RX:*` plus their matching `ACK:AUDIO:<track>`.
- Servo motion now uses 2-degree steps at 10ms intervals, including the return
  to HOME, then settles for 250ms and detaches to reduce post-sort vibration.
- Measured full-cycle ACK times: `O=3500ms`, `R=3390ms`, `I=3500ms`, all below
  the desktop `4500ms` timeout.
- Evidence: `audit/hardware/uart-audio-only-post-flash-20260613.json` and
  `audit/hardware/uart-servo-smooth-final-20260613.json`.

## Evidence Handling Policy

- Keep raw screenshots, generated JSON reports, and one-off camera captures
  local under `audit/` unless a reviewer explicitly asks for a specific
  artifact.
- When sharing evidence in Git, summarize the run in this checklist or a
  curated report under `reports/`; do not commit raw local DBs, device configs,
  session tokens, `.env*`, or screenshots that expose private account data.
- A hardware acceptance note should include date, COM port, firmware profile,
  commands tested, measured ACK times, observed audio track numbers, and whether
  the desktop/web UI showed the same route payloads.
- A failed run should record the first failing command and the observed board
  reply. Avoid hiding flaky hardware behavior behind a passing later rerun.

## App Manual Hardware Test

1. Start one local agent.
2. Open web or desktop Settings.
3. Refresh devices and choose the CH340 USB port.
4. Click `Reconnect UART`.
5. Confirm diagnostics:
   - firmware profile is `LEGACY_2_SERVO_OPENSMART`;
   - UART ACK timeout is `4500ms` or at least `3000ms`;
   - recent PONG age is fresh;
   - warning is empty.
6. Run raw D6/D7 calibration buttons and confirm Wait/Huu co/Vo co/Tai che are distinct physical positions.
7. Run Test Huu co, Test Vo co, Test Tai che.
8. Confirm payload, port, ACK, elapsed time, audio, and servo movement.

## If Only Two Dump Directions Appear

The app/firmware sends three route pairs:

- Huu co: D6=90, D7=180.
- Vo co: D6=90, D7=0.
- Tai che: D6=145, D7=180.

If any two routes look identical, inspect both D6 and D7 because the production angles now use different D7 endpoints for Huu co and Vo co. Run the 3x3 raw sweep:

- D6=45/90/145 with D7=45.
- D6=45/90/145 with D7=85.
- D6=45/90/145 with D7=180.

If changing D6 does not visibly change the path, check the D6 signal wire, D6 servo power, servo horn mounting, common GND, and mechanical linkage. If changing D6 works but the selected angles are too close, choose three distinct pairs from the sweep and update `firmware/arduino_servo/arduino_servo.ino` plus `app/core/hardware_profile.py`.

## Production Acceptance Gate

Before using camera-driven actuation with real waste, confirm all items below:

- Exactly one external USB camera is selected; laptop webcams remain disabled.
- Exactly one eligible USB/Arduino/CH340 serial port is selected or auto-saved.
- `PING` returns `PONG` from the same port used by the app.
- Manual `O`, `R`, and `I` tests each return the matching `ACK:<cmd>` within
  the configured desktop timeout.
- OPEN-SMART startup/sort/warning/proximity tracks play from the hardware board,
  and laptop MP3 preview remains servo-safe.
- Actuation Test Mode is enabled only for supervised camera-to-servo testing.
- ROI, stable-frame guard, cooldown, empty-tray re-arm, and busy/ACK handling
  are visible in Live status before placing real objects into the tray.

## Camera To Actuator E2E

1. Enable Actuation Test Mode.
2. In Settings, enable ROI and set `x/y/width/height` around only the tray.
   ROI width and height must be greater than zero.
3. Start camera live with an empty tray and wait at least 2 seconds / 10 frames
   so the dispatch guard can arm.
4. Place one representative item at a time inside the ROI:
   - Huu co: `Organic`.
   - Tai che: `Plastic bottle` or `Paper`.
   - Vo co: `Disposable tableware`, `Ceramic`, or `Unknown object` fallback
     for a pen while the production model still lacks `Pen`.
5. Confirm UI chain:
   - detected class;
   - group;
   - bin;
   - serial payload;
   - UART sent;
   - ACK;
   - history row.
6. Verify the latest three history rows contain class, group, bin, command, payload, ACK, RTT, timestamp.
7. Leave the object visible in the tray after the first dump. Confirm no second
   camera-driven UART command is sent until the tray is empty for the re-arm
   period and the global 12 second cooldown has passed.
8. Move the object outside the ROI while still visible in camera. Confirm Live
   may render it, but status shows a guard reason such as `outside ROI` and no
   UART command is sent.
9. Disable ROI and repeat one frame. Confirm status shows `ROI OFF` and no
   camera-driven UART command is sent.

Wrong model labels are data/retraining issues, not hardware failures. Capture them for later review.

## Stability Soak

- Run one agent for 20-30 minutes with UART connected.
- Confirm no duplicate `run_agent.py`.
- Confirm no new `Access is denied`.
- Confirm diagnostics still show recent PONG/profile.
- Do not continuously actuate servos during soak.
