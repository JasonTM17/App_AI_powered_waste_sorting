# arduino_servo

Firmware cho board Arduino theo so do block ma nguoi dung gui.

## Hardware Profile

Selected profile: `LEGACY_2_SERVO_OPENSMART`.

- Serial baud: `9600`.
- OPEN-SMART Serial MP3 Player A active mode from real probe: Arduino TX pin `D5` to MP3 RX, Arduino RX pin `D4` from MP3 TX. The firmware still has `MP3:MODE:PRIMARY` for the original D4/D5 block-diagram mode.
- Servo gate:
  - Servo A: `D6`.
  - Servo B: `D7`.
- Servos are not attached during firmware startup. They attach only for
  `huuco`/`voco`/`taiche`, `HOME`, `ANGLE`, and `SORTTEST`. After a sort they
  move to the dump angle and back to HOME in small interpolated steps. At HOME
  they settle briefly, then detach at idle to stop post-sort hunting/jitter.
- Proximity sensors, active LOW, audio only:
  - Huu co: `D10`, audio track `5`.
  - Tai che: `D11`, audio track `6`.
  - Vo co: `D12`, audio track `7`.
- Multi-object warning audio: track `8`, no servo movement. Generated repo
  asset: `assets/audio/gd5800/0008-multi-object-warning.mp3`.
- Servo power: use external 5V supply for servos and connect common GND with Arduino.

## Servo Angles

| State | D6 | D7 |
|---|---:|---:|
| Wait/upright after dump | 90 | 85 |
| Huu co `O` | 90 | 180 |
| Firmware `voco` / app `R` Vo co | 90 | 0 |
| Firmware `taiche` / app `I` Tai che | 160 | 180 |

## Protocol

Open Serial Monitor at `9600` baud, line ending `Newline`.

| Send | Expected result |
|---|---|
| `PING` | `PONG` |
| `PROFILE` | `PROFILE:LEGACY_2_SERVO_OPENSMART` and `MP3:PROTO:open_smart_serial_mp3_a` |
| `MP3:MODE:PRIMARY` | test Arduino RX D5 / TX D4 |
| `MP3:MODE:REVERSE` | use detected working Arduino RX D4 / TX D5 |
| `MP3:ONLINE` | query TF card/device online state and log `MP3RX:*` when the red board replies |
| `MP3:STATUS` | query playback status and log `MP3RX:*` |
| `MP3:TF` | select TF card with `7E 03 35 01 EF`, then `ACK:MP3:TF` |
| `MP3:VOL:30` | set volume 30 with `7E 03 31 1E EF`, then `ACK:MP3:VOL:30` |
| `MP3:PLAY:1` | play track 1 with `7E 04 41 00 01 EF`, then `ACK:MP3:PLAY:1` |
| `MP3:PLAYVOL:30:1` | play track 1 with volume frame `7E 04 31 1E 01 EF`, then `ACK:MP3:PLAYVOL:1` |
| `huuco` | track 2, D6/D7 move to Huu co angles, then `ACK:O` |
| `taiche` | track 3, D6/D7 move to firmware Tai che angles, then `ACK:I` |
| `voco` | track 4, D6/D7 move to firmware Vo co angles, then `ACK:R` |
| `SORT:O:0.90` | firmware-mode same as `huuco` |
| `SORT:R:0.90` | firmware-mode same as `voco` |
| `SORT:I:0.90` | firmware-mode same as `taiche` |
| `SORTSILENT:O` | move to Huu co angles without hardware sort audio, then `ACK:O` |
| `SORTSILENT:R` | move to Vo co angles without hardware sort audio, then `ACK:R` |
| `SORTSILENT:I` | move to Tai che angles without hardware sort audio, then `ACK:I` |
| `AUDIO:5` | play Huu co sensor audio only, no servo, then `ACK:AUDIO:5` |
| `AUDIO:6` | play Tai che sensor audio only, no servo, then `ACK:AUDIO:6` |
| `AUDIO:7` | play Vo co sensor audio only, no servo, then `ACK:AUDIO:7` |
| `AUDIO:8` | play multi-object warning audio only, no servo, then `ACK:AUDIO:8` |
| `ANGLE:90:85` | raw wait/upright-position test, then `ACK:ANGLE:90:85` |
| `HOME:90:85` | set temporary home/upright candidate and return `ACK:HOME:90:85` |
| `ANGLE:90:180` | raw Huu co angle test, then `ACK:ANGLE:90:180` |
| `ANGLE:90:0` | raw firmware Vo co angle test, then `ACK:ANGLE:90:0` |
| `ANGLE:160:180` | raw firmware Tai che angle test, then `ACK:ANGLE:160:180` |
| `SORTTEST:R:90:0` | play app Vo co track, test candidate dump angle, return home, then `ACK:SORTTEST:R:90:0` |
| `HOME` | attach servos, return to wait position, wait for settle, detach, then `ACK:HOME` |

The firmware logs `MP3TX:<hex>` before each MP3 command and best-effort `MP3RX:<hex>` if the red board replies. Proximity sensors send `PROX:O`, `PROX:I`, or `PROX:R` and play tracks `5/6/7`. Track `8` is reserved for the app multi-object warning. They are edge-triggered with cooldown, do not call sort logic, and do not move D6/D7. If a sensor fires while sorting, prox audio is queued until the servo returns home.

The firmware keeps `SERVO_DETACH_WHEN_IDLE=true`. Motion uses 2-degree steps
at 10 ms intervals, including the return to HOME. The dump angle is held for
1.8 seconds, HOME settles for 250 ms, then idle detach stops post-sort buzzing.
This keeps the full cycle below the desktop's 4.5-second ACK timeout.

App `plain_group` mode keeps command meaning aligned end-to-end: app `R` sends `voco\n` and expects firmware `ACK:R`; app `I` sends `taiche\n` and expects firmware `ACK:I`.

## Build & Flash

1. Close desktop app, web agent, and Serial Monitor before upload.
2. Open `arduino_servo.ino` in Arduino IDE.
3. Select the CH340 board port, usually `COM7` or `COM8`.
4. Verify first.
5. Upload.
6. If Uno upload fails with bootloader timeout, retry as Nano old bootloader.

## App Test

1. Close Serial Monitor.
2. Start one app agent only.
3. Open web or desktop Settings.
4. Click reconnect UART.
5. Confirm diagnostics show `PROFILE:LEGACY_2_SERVO_OPENSMART`.
6. Test home candidates until the tray is upright.
7. Test `SORTTEST:R` candidates until Vo co dumps toward the user's indicated bin direction.
8. Test O/R/I buttons and confirm ACK plus physical servo/audio behavior.
