/*
 * Trash Sorter Desktop v2 — firmware Arduino mẫu
 *
 * Protocol (text, newline-terminated):
 *   App -> Board: SORT:<cmd>:<conf>\n   ví dụ "SORT:S:0.92"
 *                  PING\n
 *   Board -> App: ACK:<cmd>\n            sau khi servo về home
 *                  NACK:<cmd>:<reason>\n
 *                  PONG\n
 *                  LOG:<text>\n          tuỳ chọn debug
 *
 * Mapping mặc định (chỉnh trong UI tab Mapping):
 *   P -> bin 1 (paper)
 *   S -> bin 2 (plastic)
 *   M -> bin 3 (metal)
 *   G -> bin 4 (glass)
 *   O -> bin 5 (organic)
 *   C -> bin 6 (cardboard)
 *
 * Phần cứng:
 *   - 6 servo SG90/MG90 trên chân D3..D8 (PWM).
 *   - Nguồn servo riêng 5V/2A; nối GND chung với Arduino.
 *   - Baud 9600 (đổi đồng bộ với app).
 */

#include <Servo.h>

const uint8_t NUM_BINS = 6;
const uint8_t SERVO_PINS[NUM_BINS] = {3, 4, 5, 6, 7, 8};
const int HOME_DEG = 0;
const int SORT_DEG = 90;
const unsigned long HOLD_MS = 500;       // giữ servo ở vị trí xả
const unsigned long ACK_TIMEOUT_MS = 200;

Servo servos[NUM_BINS];

// chuyển ký tự lệnh -> chỉ số bin (0..5). -1 nếu không hợp lệ.
int8_t cmd_to_bin(char c) {
  switch (c) {
    case 'P': return 0;
    case 'S': return 1;
    case 'M': return 2;
    case 'G': return 3;
    case 'O': return 4;
    case 'C': return 5;
    default:  return -1;
  }
}

void setup() {
  Serial.begin(9600);
  for (uint8_t i = 0; i < NUM_BINS; ++i) {
    servos[i].attach(SERVO_PINS[i]);
    servos[i].write(HOME_DEG);
  }
  delay(300);
  Serial.println(F("LOG:firmware ready"));
}

String buf;

void handle_line(const String &line) {
  if (line == "PING") {
    Serial.println(F("PONG"));
    return;
  }
  if (line.startsWith("SORT:")) {
    int p1 = line.indexOf(':', 5);
    if (p1 < 0) {
      Serial.println(F("NACK::malformed"));
      return;
    }
    String cmd_s = line.substring(5, p1);
    if (cmd_s.length() != 1) {
      Serial.print(F("NACK:")); Serial.print(cmd_s); Serial.println(F(":bad_cmd"));
      return;
    }
    char cmd = cmd_s.charAt(0);
    int8_t bin = cmd_to_bin(cmd);
    if (bin < 0) {
      Serial.print(F("NACK:")); Serial.print(cmd); Serial.println(F(":unknown_cmd"));
      return;
    }
    // chạy servo
    servos[bin].write(SORT_DEG);
    delay(HOLD_MS);
    servos[bin].write(HOME_DEG);
    delay(120);
    Serial.print(F("ACK:"));
    Serial.println(cmd);
    return;
  }
  // bỏ qua dòng lạ
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (buf.length() > 0) {
        handle_line(buf);
        buf = "";
      }
    } else if (buf.length() < 64) {
      buf += c;
    } else {
      // overflow — reset
      buf = "";
      Serial.println(F("LOG:overflow"));
    }
  }
}
