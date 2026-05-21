# arduino_servo

Firmware mẫu cho board điều khiển servo phân loại rác. Tương thích app Trash Sorter Desktop v2.

## Phần cứng

- Arduino Uno / Nano / ESP32 (test trên Uno R3).
- 6 servo SG90/MG90 trên chân digital 3..8.
- Nguồn 5V/2A riêng cho servo; **GND nối chung với Arduino**.
- USB cáp (cổng COM) tới máy chạy app.

## Build & flash

1. Mở `arduino_servo.ino` trong Arduino IDE 2.x.
2. Cài thư viện `Servo` (built-in).
3. Board → Arduino Uno (hoặc tương ứng), cổng COM đúng.
4. Verify → Upload.

## Test bằng tay

Mở Serial Monitor 9600 baud, line ending `Newline`.
- Gõ `PING` → board trả `PONG`.
- Gõ `SORT:S:0.90` → servo 2 quay 90°, giữ 500ms, về 0°, board trả `ACK:S`.

## Mapping

| Cmd | Bin | Pin |
|---|---|---|
| P | 1 paper | D3 |
| S | 2 plastic | D4 |
| M | 3 metal | D5 |
| G | 4 glass | D6 |
| O | 5 organic | D7 |
| C | 6 cardboard | D8 |

Chỉnh trong file `arduino_servo.ino` nếu phần cứng khác.

## Protocol

Xem `docs/adr/0004-uart-text-protocol.md` ở repo gốc.
