/*
 * Trash Sorter Pro - OPEN-SMART Serial MP3 Player A firmware.
 *
 * Source of truth:
 *   - User's two visual block screenshots.
 *   - Real hardware photo showing red OPEN-SMART Serial MP3 Player A.
 *
 * Hardware:
 *   Serial baud: 9600
 *   OPEN-SMART MP3 detected active mode: Arduino TX D5 -> MP3 RX,
 *   Arduino RX D4 <- MP3 TX. Primary D4/D5 mode is still available for tests.
 *   Servo gate A: D6
 *   Servo gate B: D7
 *   Audio-only full/proximity sensors: D10, D11, D12 active LOW
 *
 * PC commands:
 *   huuco   -> track 2, D6=90,  D7=180, then wait position
 *   voco    -> track 4, D6=90,  D7=0,   then wait position
 *   taiche  -> track 3, D6=160, D7=180, then wait position
 *   SORTSILENT:<O|R|I> -> same servo route without hardware audio
 *
 * Sensor audio:
 *   D10 LOW -> track 5
 *   D11 LOW -> track 6
 *   D12 LOW -> track 7
 * Warning audio:
 *   AUDIO:8 -> multi-object warning, no servo movement
 *   These sensor events never move D6/D7. Only serial sort commands move servos.
 *
 * Extra diagnostics:
 *   PING, PROFILE, AUDIO:<track>, MP3:TF, MP3:VOL:<0..30>,
 *   MP3:PLAY:<1..255>, MP3:PLAYVOL:<1..255>, MP3:ONLINE, MP3:STATUS,
 *   MP3:NEXT, MP3:RESET, MP3:MODE:PRIMARY, MP3:MODE:REVERSE,
 *   ANGLE:<D6>:<D7>, HOME, HOME:<D6>:<D7>, SORTTEST:<O|R|I>:<D6>:<D7>
 */

#include <Servo.h>
#include <SoftwareSerial.h>

const char PROFILE_ID[] = "LEGACY_2_SERVO_OPENSMART";
const char AUDIO_PROTOCOL[] = "open_smart_serial_mp3_a";

const uint8_t MP3_TX_PIN = 4;
const uint8_t MP3_RX_PIN = 5;
const uint8_t SERVO_A_PIN = 6;
const uint8_t SERVO_B_PIN = 7;
const uint8_t SENSOR_HUUCO_PIN = 10;
const uint8_t SENSOR_TAICHE_PIN = 11;
const uint8_t SENSOR_VOCO_PIN = 12;

const int SERVO_A_WAIT_DEFAULT = 90;
const int SERVO_B_WAIT_DEFAULT = 85;
const uint8_t DEFAULT_VOLUME = 30;
const unsigned long SORT_HOLD_MS = 1800;
const unsigned long SENSOR_AUDIO_COOLDOWN_MS = 2000;
const unsigned long CALIBRATION_HOLD_MS = 1800;
const unsigned long PRE_SORT_HOME_SETTLE_MS = 0;
const unsigned long RETURN_SETTLE_MS = 250;
const unsigned long MP3_RESPONSE_WINDOW_MS = 260;
const unsigned long SERVO_ATTACH_SETTLE_MS = 100;
const int SERVO_MOVE_STEP_DEGREES = 2;
const unsigned long SERVO_MOVE_STEP_MS = 10;
const bool SERVO_DETACH_WHEN_IDLE = true;

Servo servoA;
Servo servoB;

int servoAWait = SERVO_A_WAIT_DEFAULT;
int servoBWait = SERVO_B_WAIT_DEFAULT;
int servoACurrent = SERVO_A_WAIT_DEFAULT;
int servoBCurrent = SERVO_B_WAIT_DEFAULT;
bool servosAttached = false;

struct SensorRuntime {
  uint8_t pin;
  char cmd;
  uint8_t track;
  bool wasLow;
  bool pendingAudio;
  unsigned long lastAudioAt;
};

SensorRuntime sensors[] = {
  {SENSOR_HUUCO_PIN, 'O', 5, false, false, 0},
  {SENSOR_TAICHE_PIN, 'I', 6, false, false, 0},
  {SENSOR_VOCO_PIN, 'R', 7, false, false, 0},
};

const uint8_t SENSOR_COUNT = sizeof(sensors) / sizeof(sensors[0]);

// SoftwareSerial order is (Arduino RX, Arduino TX).
// The old visual block says "TXPIN 4 / RXPIN 5", but real boards are often
// wired opposite. Keep both orientations so we can diagnose without rewiring.
SoftwareSerial mp3Primary(MP3_RX_PIN, MP3_TX_PIN);
SoftwareSerial mp3Reverse(MP3_TX_PIN, MP3_RX_PIN);
SoftwareSerial *activeMp3 = &mp3Primary;
bool mp3ReverseMode = false;

String serialBuffer;
bool sortInProgress = false;

void poll_sensors();
void delay_with_sensor_polling(unsigned long durationMs);

void print_hex_byte(uint8_t value) {
  if (value < 0x10) {
    Serial.print('0');
  }
  Serial.print(value, HEX);
}

void print_frame(const char *label, const uint8_t *frame, uint8_t length) {
  Serial.print(label);
  Serial.print(F(":"));
  for (uint8_t i = 0; i < length; i++) {
    if (i > 0) {
      Serial.print(' ');
    }
    print_hex_byte(frame[i]);
  }
  Serial.println();
}

void read_mp3_response(unsigned long windowMs) {
  unsigned long started = millis();
  bool startedLine = false;
  while (millis() - started < windowMs) {
    while (activeMp3->available() > 0) {
      uint8_t b = (uint8_t)activeMp3->read();
      if (!startedLine) {
        Serial.print(F("MP3RX:"));
        startedLine = true;
      } else {
        Serial.print(' ');
      }
      print_hex_byte(b);
    }
    delay(1);
  }
  if (startedLine) {
    Serial.println();
  }
}

void open_smart_send(const uint8_t *frame, uint8_t length) {
  activeMp3->listen();
  print_frame("MP3TX", frame, length);
  for (uint8_t i = 0; i < length; i++) {
    activeMp3->write(frame[i]);
  }
  activeMp3->flush();
  read_mp3_response(MP3_RESPONSE_WINDOW_MS);
}

void set_mp3_mode(bool reverse) {
  mp3ReverseMode = reverse;
  activeMp3 = reverse ? &mp3Reverse : &mp3Primary;
  activeMp3->begin(9600);
  activeMp3->listen();
  Serial.print(F("MP3:MODE:"));
  Serial.println(reverse ? F("REVERSE_RX_D4_TX_D5") : F("PRIMARY_RX_D5_TX_D4"));
}

void open_smart_select_tf() {
  const uint8_t frame[] = {0x7E, 0x03, 0x35, 0x01, 0xEF};
  open_smart_send(frame, sizeof(frame));
  Serial.println(F("MP3:TF"));
}

void open_smart_set_volume(uint8_t volume) {
  if (volume > 30) {
    volume = 30;
  }
  const uint8_t frame[] = {0x7E, 0x03, 0x31, volume, 0xEF};
  open_smart_send(frame, sizeof(frame));
  Serial.print(F("MP3:VOL:"));
  Serial.println(volume);
}

void open_smart_play_index(uint8_t track) {
  if (track == 0) {
    Serial.println(F("MP3:ERR:bad_track"));
    return;
  }
  const uint8_t frame[] = {0x7E, 0x04, 0x41, 0x00, track, 0xEF};
  open_smart_send(frame, sizeof(frame));
  Serial.print(F("MP3:PLAY:"));
  Serial.println(track);
}

void open_smart_play_with_volume(uint8_t track, uint8_t volume) {
  if (track == 0) {
    Serial.println(F("MP3:ERR:bad_track"));
    return;
  }
  if (volume > 30) {
    volume = 30;
  }
  const uint8_t frame[] = {0x7E, 0x04, 0x31, volume, track, 0xEF};
  open_smart_send(frame, sizeof(frame));
  Serial.print(F("MP3:PLAYVOL:"));
  Serial.print(volume);
  Serial.print(F(":"));
  Serial.println(track);
}

void open_smart_next() {
  const uint8_t frame[] = {0x7E, 0x02, 0x03, 0xEF};
  open_smart_send(frame, sizeof(frame));
  Serial.println(F("MP3:NEXT"));
}

void open_smart_get_status() {
  const uint8_t frame[] = {0x7E, 0x02, 0x10, 0xEF};
  open_smart_send(frame, sizeof(frame));
  Serial.println(F("MP3:STATUS"));
}

void open_smart_get_online_device() {
  const uint8_t frame[] = {0x7E, 0x02, 0x18, 0xEF};
  open_smart_send(frame, sizeof(frame));
  Serial.println(F("MP3:ONLINE"));
}

void open_smart_reset_chip() {
  const uint8_t frame[] = {0x7E, 0x03, 0x35, 0x05, 0xEF};
  open_smart_send(frame, sizeof(frame));
  Serial.println(F("MP3:RESET"));
}

void print_audio_event(const char *cmd, uint8_t track, const char *source) {
  Serial.print(F("AUDIO:"));
  Serial.print(cmd);
  Serial.print(F(":"));
  Serial.print(track);
  Serial.print(F(":"));
  Serial.println(source);
}

void print_audio_event(char cmd, uint8_t track, const char *source) {
  char cmdText[2] = {cmd, '\0'};
  print_audio_event(cmdText, track, source);
}

void play_track_logged(uint8_t track, const char *cmd, const char *source) {
  open_smart_play_index(track);
  print_audio_event(cmd, track, source);
}

void play_track_logged(uint8_t track, char cmd, const char *source) {
  open_smart_play_index(track);
  print_audio_event(cmd, track, source);
}

bool valid_angle(int angle) {
  return angle >= 0 && angle <= 180;
}

void release_servo_signal_pins() {
  digitalWrite(SERVO_A_PIN, LOW);
  digitalWrite(SERVO_B_PIN, LOW);
  pinMode(SERVO_A_PIN, OUTPUT);
  pinMode(SERVO_B_PIN, OUTPUT);
}

void ensure_servos_attached() {
  if (servosAttached) {
    return;
  }
  // Cache the home angle before attach so serial reset/startup does not make
  // the servos hunt from an undefined pulse width.
  servoA.write(servoACurrent);
  servoB.write(servoBCurrent);
  servoA.attach(SERVO_A_PIN);
  servoB.attach(SERVO_B_PIN);
  servosAttached = true;
  delay(SERVO_ATTACH_SETTLE_MS);
}

void idle_servos() {
  if (!SERVO_DETACH_WHEN_IDLE || !servosAttached) {
    return;
  }
  servoA.detach();
  servoB.detach();
  release_servo_signal_pins();
  servosAttached = false;
}

void move_servos_smooth(int servoATarget, int servoBTarget) {
  ensure_servos_attached();
  int startA = servoACurrent;
  int startB = servoBCurrent;
  int maxDelta = max(abs(servoATarget - startA), abs(servoBTarget - startB));
  int steps = max(1, (maxDelta + SERVO_MOVE_STEP_DEGREES - 1) / SERVO_MOVE_STEP_DEGREES);

  for (int step = 1; step <= steps; step++) {
    int nextA = startA + ((servoATarget - startA) * step) / steps;
    int nextB = startB + ((servoBTarget - startB) * step) / steps;
    servoA.write(nextA);
    servoB.write(nextB);
    servoACurrent = nextA;
    servoBCurrent = nextB;
    delay_with_sensor_polling(SERVO_MOVE_STEP_MS);
  }
}

void move_to_wait() {
  move_servos_smooth(servoAWait, servoBWait);
}

bool is_uint_string(const String &value) {
  if (value.length() == 0) {
    return false;
  }
  for (unsigned int i = 0; i < value.length(); i++) {
    if (!isDigit(value.charAt(i))) {
      return false;
    }
  }
  return true;
}

char plain_to_cmd(const String &line) {
  if (line == "huuco") {
    return 'O';
  }
  if (line == "taiche") {
    return 'I';
  }
  if (line == "voco") {
    return 'R';
  }
  return '\0';
}

uint8_t sort_track_for_cmd(char cmd) {
  switch (cmd) {
    case 'O': return 2;
    case 'R': return 4;
    case 'I': return 3;
    default: return 0;
  }
}

void servo_position_for_cmd(char cmd, int &servoAValue, int &servoBValue) {
  switch (cmd) {
    case 'O':
      servoAValue = 90;
      servoBValue = 180;
      return;
    case 'R':
      servoAValue = 90;
      servoBValue = 0;
      return;
    case 'I':
      servoAValue = 160;
      servoBValue = 180;
      return;
    default:
      servoAValue = servoAWait;
      servoBValue = servoBWait;
      return;
  }
}

void flush_pending_sensor_audio() {
  for (uint8_t i = 0; i < SENSOR_COUNT; i++) {
    if (!sensors[i].pendingAudio) {
      continue;
    }
    sensors[i].pendingAudio = false;
    play_track_logged(sensors[i].track, sensors[i].cmd, "prox");
    delay(20);
  }
}

void run_sort(char cmd, bool playAudio) {
  if (sortInProgress) {
    Serial.print(F("NACK:"));
    Serial.print(cmd);
    Serial.println(F(":busy"));
    return;
  }
  uint8_t track = sort_track_for_cmd(cmd);
  if (track == 0) {
    Serial.print(F("NACK:"));
    Serial.print(cmd);
    Serial.println(F(":unknown_cmd"));
    return;
  }

  sortInProgress = true;
  int servoAValue = servoAWait;
  int servoBValue = servoBWait;
  servo_position_for_cmd(cmd, servoAValue, servoBValue);

  move_to_wait();
  delay_with_sensor_polling(PRE_SORT_HOME_SETTLE_MS);
  if (playAudio) {
    play_track_logged(track, cmd, "sort");
  }
  move_servos_smooth(servoAValue, servoBValue);
  delay_with_sensor_polling(SORT_HOLD_MS);
  move_to_wait();
  delay(RETURN_SETTLE_MS);
  idle_servos();
  sortInProgress = false;
  flush_pending_sensor_audio();

  Serial.print(F("ACK:"));
  Serial.println(cmd);
}

void run_angle_test(int servoAValue, int servoBValue) {
  if (!valid_angle(servoAValue) || !valid_angle(servoBValue)) {
    Serial.println(F("NACK:ANGLE:angle_out_of_range"));
    return;
  }

  move_servos_smooth(servoAValue, servoBValue);
  delay(CALIBRATION_HOLD_MS);
  move_to_wait();
  delay(RETURN_SETTLE_MS);
  idle_servos();

  Serial.print(F("ACK:ANGLE:"));
  Serial.print(servoAValue);
  Serial.print(F(":"));
  Serial.println(servoBValue);
}

void run_sort_angle_test(char cmd, int servoAValue, int servoBValue) {
  if (sortInProgress) {
    Serial.print(F("NACK:SORTTEST:"));
    Serial.print(cmd);
    Serial.println(F(":busy"));
    return;
  }
  if (!valid_angle(servoAValue) || !valid_angle(servoBValue)) {
    Serial.println(F("NACK:SORTTEST:angle_out_of_range"));
    return;
  }
  uint8_t track = sort_track_for_cmd(cmd);
  if (track == 0) {
    Serial.print(F("NACK:SORTTEST:"));
    Serial.print(cmd);
    Serial.println(F(":unknown_cmd"));
    return;
  }

  sortInProgress = true;
  play_track_logged(track, cmd, "sorttest");
  move_to_wait();
  delay_with_sensor_polling(PRE_SORT_HOME_SETTLE_MS);
  move_servos_smooth(servoAValue, servoBValue);
  delay_with_sensor_polling(SORT_HOLD_MS);
  move_to_wait();
  delay(RETURN_SETTLE_MS);
  idle_servos();
  sortInProgress = false;
  flush_pending_sensor_audio();

  Serial.print(F("ACK:SORTTEST:"));
  Serial.print(cmd);
  Serial.print(F(":"));
  Serial.print(servoAValue);
  Serial.print(F(":"));
  Serial.println(servoBValue);
}

void set_home_position(int servoAValue, int servoBValue) {
  if (!valid_angle(servoAValue) || !valid_angle(servoBValue)) {
    Serial.println(F("NACK:HOME:angle_out_of_range"));
    return;
  }
  servoAWait = servoAValue;
  servoBWait = servoBValue;
  move_to_wait();
  delay(RETURN_SETTLE_MS);
  idle_servos();

  Serial.print(F("ACK:HOME:"));
  Serial.print(servoAWait);
  Serial.print(F(":"));
  Serial.println(servoBWait);
}

void publish_profile() {
  Serial.print(F("PROFILE:"));
  Serial.println(PROFILE_ID);
  Serial.print(F("MP3:PROTO:"));
  Serial.println(AUDIO_PROTOCOL);
  Serial.print(F("MP3:MODE:"));
  Serial.println(mp3ReverseMode ? F("REVERSE_RX_D4_TX_D5") : F("PRIMARY_RX_D5_TX_D4"));
  Serial.print(F("SERVO:HOME:"));
  Serial.print(servoAWait);
  Serial.print(F(":"));
  Serial.println(servoBWait);
  Serial.print(F("SERVO:IDLE:"));
  Serial.println(SERVO_DETACH_WHEN_IDLE ? F("DETACH") : F("HOLD"));
}

void handle_sensor(SensorRuntime &sensor, bool allowAudioNow) {
  bool isLow = digitalRead(sensor.pin) == LOW;
  unsigned long now = millis();
  if (isLow && !sensor.wasLow && now - sensor.lastAudioAt >= SENSOR_AUDIO_COOLDOWN_MS) {
    sensor.lastAudioAt = now;
    Serial.print(F("PROX:"));
    Serial.println(sensor.cmd);
    if (allowAudioNow && !sortInProgress) {
      play_track_logged(sensor.track, sensor.cmd, "prox");
    } else {
      sensor.pendingAudio = true;
      Serial.print(F("LOG:prox audio queued "));
      Serial.println(sensor.cmd);
    }
  }
  sensor.wasLow = isLow;
}

void poll_sensors(bool allowAudioNow) {
  for (uint8_t i = 0; i < SENSOR_COUNT; i++) {
    handle_sensor(sensors[i], allowAudioNow);
  }
}

void poll_sensors() {
  poll_sensors(true);
}

void delay_with_sensor_polling(unsigned long durationMs) {
  unsigned long started = millis();
  while (millis() - started < durationMs) {
    poll_sensors(false);
    delay(10);
  }
}

void handle_mp3_command(const String &line) {
  if (line == "MP3:MODE?") {
    Serial.print(F("ACK:MP3:MODE:"));
    Serial.println(mp3ReverseMode ? F("REVERSE") : F("PRIMARY"));
    publish_profile();
    return;
  }

  if (line == "MP3:MODE:PRIMARY" || line == "MP3:MODE:0") {
    set_mp3_mode(false);
    Serial.println(F("ACK:MP3:MODE:PRIMARY"));
    return;
  }

  if (line == "MP3:MODE:REVERSE" || line == "MP3:MODE:1") {
    set_mp3_mode(true);
    Serial.println(F("ACK:MP3:MODE:REVERSE"));
    return;
  }

  if (line == "MP3:TF") {
    open_smart_select_tf();
    Serial.println(F("ACK:MP3:TF"));
    return;
  }

  if (line.startsWith("MP3:VOL:")) {
    String volumeText = line.substring(8);
    if (!is_uint_string(volumeText)) {
      Serial.println(F("NACK:MP3:VOL:malformed"));
      return;
    }
    int volume = volumeText.toInt();
    if (volume < 0 || volume > 30) {
      Serial.println(F("NACK:MP3:VOL:out_of_range"));
      return;
    }
    open_smart_set_volume((uint8_t)volume);
    Serial.print(F("ACK:MP3:VOL:"));
    Serial.println(volume);
    return;
  }

  if (line == "MP3:NEXT") {
    open_smart_next();
    Serial.println(F("ACK:MP3:NEXT"));
    return;
  }

  if (line == "MP3:STATUS") {
    open_smart_get_status();
    Serial.println(F("ACK:MP3:STATUS"));
    return;
  }

  if (line == "MP3:ONLINE") {
    open_smart_get_online_device();
    Serial.println(F("ACK:MP3:ONLINE"));
    return;
  }

  if (line == "MP3:RESET") {
    open_smart_reset_chip();
    delay(500);
    open_smart_select_tf();
    delay(120);
    open_smart_set_volume(DEFAULT_VOLUME);
    Serial.println(F("ACK:MP3:RESET"));
    return;
  }

  if (line.startsWith("MP3:PLAYVOL:")) {
    String tail = line.substring(12);
    int separator = tail.indexOf(':');
    String volumeText = separator >= 0 ? tail.substring(0, separator) : String(DEFAULT_VOLUME);
    String trackText = separator >= 0 ? tail.substring(separator + 1) : tail;
    if (!is_uint_string(volumeText) || !is_uint_string(trackText)) {
      Serial.println(F("NACK:MP3:PLAYVOL:malformed"));
      return;
    }
    int volume = volumeText.toInt();
    int track = trackText.toInt();
    if (volume < 0 || volume > 30 || track < 1 || track > 255) {
      Serial.println(F("NACK:MP3:PLAYVOL:out_of_range"));
      return;
    }
    open_smart_play_with_volume((uint8_t)track, (uint8_t)volume);
    Serial.print(F("ACK:MP3:PLAYVOL:"));
    Serial.println(track);
    return;
  }

  if (line.startsWith("MP3:PLAY:")) {
    String trackText = line.substring(9);
    if (!is_uint_string(trackText)) {
      Serial.println(F("NACK:MP3:PLAY:malformed"));
      return;
    }
    int track = trackText.toInt();
    if (track < 1 || track > 255) {
      Serial.println(F("NACK:MP3:PLAY:out_of_range"));
      return;
    }
    play_track_logged((uint8_t)track, "MANUAL", "manual");
    Serial.print(F("ACK:MP3:PLAY:"));
    Serial.println(track);
    return;
  }

  Serial.println(F("NACK:MP3:unknown"));
}

void handle_line(String line) {
  line.trim();
  if (line.length() == 0) {
    return;
  }

  if (line == "PING") {
    Serial.println(F("PONG"));
    return;
  }

  if (line == "PROFILE") {
    publish_profile();
    return;
  }

  if (line == "HOME") {
    move_to_wait();
    delay(RETURN_SETTLE_MS);
    idle_servos();
    Serial.println(F("ACK:HOME"));
    return;
  }

  if (line.startsWith("HOME:")) {
    int firstSeparator = line.indexOf(':', 5);
    if (firstSeparator < 0) {
      Serial.println(F("NACK:HOME:malformed"));
      return;
    }
    String servoAText = line.substring(5, firstSeparator);
    String servoBText = line.substring(firstSeparator + 1);
    if (!is_uint_string(servoAText) || !is_uint_string(servoBText)) {
      Serial.println(F("NACK:HOME:malformed"));
      return;
    }
    set_home_position(servoAText.toInt(), servoBText.toInt());
    return;
  }

  if (line.startsWith("MP3:")) {
    handle_mp3_command(line);
    return;
  }

  if (line.startsWith("AUDIO:")) {
    String trackText = line.substring(6);
    if (!is_uint_string(trackText)) {
      Serial.println(F("NACK:AUDIO:malformed"));
      return;
    }
    int track = trackText.toInt();
    if (track < 1 || track > 8) {
      Serial.println(F("NACK:AUDIO:track_out_of_range"));
      return;
    }
    play_track_logged((uint8_t)track, "MANUAL", "manual");
    delay(80);
    Serial.print(F("ACK:AUDIO:"));
    Serial.println(track);
    return;
  }

  char plainCmd = plain_to_cmd(line);
  if (plainCmd != '\0') {
    run_sort(plainCmd, true);
    return;
  }

  if (line.startsWith("SORTSILENT:")) {
    String cmdText = line.substring(11);
    if (cmdText.length() != 1) {
      Serial.println(F("NACK:SORTSILENT:bad_cmd"));
      return;
    }
    run_sort(cmdText.charAt(0), false);
    return;
  }

  if (line.startsWith("SORT:")) {
    int firstSeparator = line.indexOf(':', 5);
    if (firstSeparator < 0) {
      Serial.println(F("NACK::malformed"));
      return;
    }
    String cmdText = line.substring(5, firstSeparator);
    if (cmdText.length() != 1) {
      Serial.print(F("NACK:"));
      Serial.print(cmdText);
      Serial.println(F(":bad_cmd"));
      return;
    }
    run_sort(cmdText.charAt(0), true);
    return;
  }

  if (line.startsWith("SORTTEST:")) {
    String tail = line.substring(9);
    int firstSeparator = tail.indexOf(':');
    int secondSeparator = firstSeparator >= 0 ? tail.indexOf(':', firstSeparator + 1) : -1;
    if (firstSeparator < 0 || secondSeparator < 0) {
      Serial.println(F("NACK:SORTTEST:malformed"));
      return;
    }
    String cmdText = tail.substring(0, firstSeparator);
    String servoAText = tail.substring(firstSeparator + 1, secondSeparator);
    String servoBText = tail.substring(secondSeparator + 1);
    if (cmdText.length() != 1 || !is_uint_string(servoAText) || !is_uint_string(servoBText)) {
      Serial.println(F("NACK:SORTTEST:malformed"));
      return;
    }
    run_sort_angle_test(cmdText.charAt(0), servoAText.toInt(), servoBText.toInt());
    return;
  }

  if (line.startsWith("ANGLE:")) {
    int firstSeparator = line.indexOf(':', 6);
    if (firstSeparator < 0) {
      Serial.println(F("NACK:ANGLE:malformed"));
      return;
    }
    String servoAText = line.substring(6, firstSeparator);
    String servoBText = line.substring(firstSeparator + 1);
    if (!is_uint_string(servoAText) || !is_uint_string(servoBText)) {
      Serial.println(F("NACK:ANGLE:malformed"));
      return;
    }
    run_angle_test(servoAText.toInt(), servoBText.toInt());
    return;
  }

  Serial.println(F("NACK::unknown_line"));
}

void setup() {
  release_servo_signal_pins();

  Serial.begin(9600);
  set_mp3_mode(true);

  pinMode(SENSOR_HUUCO_PIN, INPUT_PULLUP);
  pinMode(SENSOR_VOCO_PIN, INPUT_PULLUP);
  pinMode(SENSOR_TAICHE_PIN, INPUT_PULLUP);
  for (uint8_t i = 0; i < SENSOR_COUNT; i++) {
    sensors[i].wasLow = digitalRead(sensors[i].pin) == LOW;
    sensors[i].lastAudioAt = millis() - SENSOR_AUDIO_COOLDOWN_MS;
  }

  delay(500);
  open_smart_select_tf();
  delay(120);
  open_smart_set_volume(DEFAULT_VOLUME);
  delay(120);
  play_track_logged(1, "START", "startup");

  Serial.println(F("MP3:READY"));
  Serial.println(F("LOG:firmware ready LEGACY_2_SERVO_OPENSMART"));
  publish_profile();
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (serialBuffer.length() > 0) {
        handle_line(serialBuffer);
        serialBuffer = "";
      }
    } else if (serialBuffer.length() < 80) {
      serialBuffer += c;
    } else {
      serialBuffer = "";
      Serial.println(F("LOG:overflow"));
    }
  }

  poll_sensors();
}
