from pathlib import Path

FIRMWARE = (
    Path(__file__).resolve().parents[2]
    / "firmware"
    / "arduino_servo"
    / "arduino_servo.ino"
)


def test_full_bin_sensors_require_sustained_trigger_and_release() -> None:
    source = FIRMWARE.read_text(encoding="utf-8")

    assert "SENSOR_TRIGGER_HOLD_MS = 2000" in source
    assert "SENSOR_RELEASE_HOLD_MS = 1000" in source
    assert "SENSOR_AUDIO_COOLDOWN_MS = 15000" in source
    assert "now - sensor.lowSince >= SENSOR_TRIGGER_HOLD_MS" in source
    assert "now - sensor.highSince >= SENSOR_RELEASE_HOLD_MS" in source


def test_proximity_event_is_emitted_only_after_hold_check() -> None:
    source = FIRMWARE.read_text(encoding="utf-8")
    hold_check = source.index("now - sensor.lowSince >= SENSOR_TRIGGER_HOLD_MS")
    event_emit = source.index('Serial.print(F("PROX:"))', hold_check)

    assert hold_check < event_emit
