from app.core.hardware_profile import hardware_profile_payload, route_for_command


def test_hardware_profile_routes_are_exact():
    profile = hardware_profile_payload()
    assert profile["profile_id"] == "LEGACY_2_SERVO_OPENSMART"
    assert profile["audio_protocol"] == "open_smart_serial_mp3_a"
    assert profile["baud"] == 9600
    assert profile["protocol"] == "plain_group"
    assert profile["gd5800"] == {
        "module": "OPEN-SMART Serial MP3 Player A",
        "audio_protocol": "open_smart_serial_mp3_a",
        "serial_mode": "REVERSE_RX_D4_TX_D5",
        "tx_pin": "D5",
        "rx_pin": "D4",
        "startup_track": 1,
        "multi_object_warning_track": 8,
        "volume_default": 30,
        "select_tf_frame": "7E 03 35 01 EF",
        "play_index_frame": "7E 04 41 00 <track> EF",
    }
    assert profile["servo"] == {
        "mode": "two_servo_gate",
        "wait_degrees": {"D6": 90, "D7": 85},
        "dump_degrees": "per_route",
        "hold_ms": 1800,
        "pre_sort_home_settle_ms": 0,
        "return_settle_ms": 250,
        "move_step_degrees": 2,
        "move_step_ms": 10,
        "idle_policy": "detach",
    }
    assert profile["routes"] == [
        {
            "command": "O",
            "label": "Huu co",
            "serial_payload": "huuco",
            "payload_line": "huuco\\n",
            "bin_index": 1,
            "servo_pin": "D6/D7",
            "servo_positions": {"D6": 90, "D7": 180},
            "gd5800_track": 2,
        },
        {
            "command": "R",
            "label": "Vo co",
            "serial_payload": "voco",
            "payload_line": "voco\\n",
            "bin_index": 2,
            "servo_pin": "D6/D7",
            "servo_positions": {"D6": 90, "D7": 0},
            "gd5800_track": 4,
        },
        {
            "command": "I",
            "label": "Tai che",
            "serial_payload": "taiche",
            "payload_line": "taiche\\n",
            "bin_index": 3,
            "servo_pin": "D6/D7",
            "servo_positions": {"D6": 145, "D7": 180},
            "gd5800_track": 3,
        },
    ]
    assert profile["bin_sensors"] == []
    assert profile["proximity_sensors"] == [
        {
            "command": "O",
            "label": "Huu co",
            "pin": "D10",
            "active_level": 0,
            "gd5800_track": 5,
            "action": "audio_only",
            "controls_servo": False,
        },
        {
            "command": "I",
            "label": "Tai che",
            "pin": "D11",
            "active_level": 0,
            "gd5800_track": 6,
            "action": "audio_only",
            "controls_servo": False,
        },
        {
            "command": "R",
            "label": "Vo co",
            "pin": "D12",
            "active_level": 0,
            "gd5800_track": 7,
            "action": "audio_only",
            "controls_servo": False,
        },
    ]


def test_route_for_command_normalizes_input():
    route = route_for_command(" r ")
    assert route is not None
    assert route.command == "R"
    assert route.serial_payload == "voco"
    assert route.bin_index == 2
    assert route_for_command("X") is None
