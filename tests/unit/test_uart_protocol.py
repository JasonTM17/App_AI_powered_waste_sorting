import pytest

from app.core.uart_protocol import (
    encode_angle_test,
    encode_audio_test,
    encode_home_test,
    encode_mp3_test,
    encode_profile_request,
    encode_sort,
    encode_sort_angle_test,
    expected_ack_command,
    parse_line,
    protocol_expects_ack,
)


def test_encode_sort_basic():
    assert encode_sort("R", 0.92) == b"SORT:R:0.92\n"


def test_encode_plain_group_for_block_firmware():
    assert encode_sort("O", 0.92, protocol="plain_group") == b"huuco\n"
    assert encode_sort("R", 0.92, protocol="plain_group") == b"voco\n"
    assert encode_sort("I", 0.92, protocol="plain_group") == b"taiche\n"
    assert protocol_expects_ack("plain_group") is True
    assert protocol_expects_ack("sort_line") is True


def test_encode_silent_sort_uses_audio_free_firmware_command():
    assert (
        encode_sort("O", 0.92, protocol="plain_group", silent=True)
        == b"SORTSILENT:O\n"
    )
    assert (
        encode_sort("R", 0.92, protocol="sort_line", silent=True)
        == b"SORTSILENT:R\n"
    )


def test_expected_ack_command_for_plain_group_payloads_matches_app_commands():
    assert expected_ack_command("O", "plain_group") == "O"
    assert expected_ack_command("R", "plain_group") == "R"
    assert expected_ack_command("I", "plain_group") == "I"
    assert expected_ack_command("R", "sort_line") == "R"


def test_encode_sort_clamps_conf():
    assert encode_sort("O", 1.5) == b"SORT:O:1.00\n"
    assert encode_sort("I", -0.1) == b"SORT:I:0.00\n"


def test_encode_sort_rejects_bad_command():
    with pytest.raises(ValueError):
        encode_sort("", 0.5)
    with pytest.raises(ValueError):
        encode_sort("AB", 0.5)


def test_parse_ack():
    msg = parse_line(b"ACK:R\n")
    assert msg == ("ack", "R", None)


def test_parse_ack_for_all_three_hardware_commands():
    assert parse_line(b"ACK:O\n") == ("ack", "O", None)
    assert parse_line(b"ACK:R\n") == ("ack", "R", None)
    assert parse_line(b"ACK:I\n") == ("ack", "I", None)


def test_parse_nack_with_reason():
    msg = parse_line(b"NACK:I:busy\n")
    assert msg == ("nack", "I", "busy")


def test_parse_pong():
    msg = parse_line(b"PONG\n")
    assert msg == ("pong", None, None)


def test_encode_profile_request():
    assert encode_profile_request() == b"PROFILE\n"


def test_encode_angle_test():
    assert encode_angle_test(90, 100) == b"ANGLE:90:100\n"


def test_encode_home_test():
    assert encode_home_test(90, 88) == b"HOME:90:88\n"


def test_encode_sort_angle_test():
    assert encode_sort_angle_test("I", 0, 180) == b"SORTTEST:I:0:180\n"


def test_encode_angle_test_rejects_out_of_range():
    with pytest.raises(ValueError):
        encode_angle_test(181, 90)
    with pytest.raises(ValueError):
        encode_home_test(90, 181)
    with pytest.raises(ValueError):
        encode_sort_angle_test("X", 90, 90)


def test_encode_audio_test():
    assert encode_audio_test(5) == b"AUDIO:5\n"
    assert encode_audio_test(8) == b"AUDIO:8\n"


def test_encode_audio_test_rejects_out_of_range():
    with pytest.raises(ValueError):
        encode_audio_test(0)
    with pytest.raises(ValueError):
        encode_audio_test(9)


def test_encode_mp3_test_commands():
    assert encode_mp3_test("TF") == b"MP3:TF\n"
    assert encode_mp3_test("VOL", 30) == b"MP3:VOL:30\n"
    assert encode_mp3_test("PLAY", 7) == b"MP3:PLAY:7\n"
    assert encode_mp3_test("PLAYVOL", 7) == b"MP3:PLAYVOL:30:7\n"
    assert encode_mp3_test("NEXT") == b"MP3:NEXT\n"
    assert encode_mp3_test("ONLINE") == b"MP3:ONLINE\n"
    assert encode_mp3_test("STATUS") == b"MP3:STATUS\n"
    assert encode_mp3_test("RESET") == b"MP3:RESET\n"
    assert encode_mp3_test("MODE_PRIMARY") == b"MP3:MODE:PRIMARY\n"
    assert encode_mp3_test("MODE_REVERSE") == b"MP3:MODE:REVERSE\n"
    assert encode_mp3_test("MODE_QUERY") == b"MP3:MODE?\n"


def test_encode_mp3_test_rejects_invalid_values():
    with pytest.raises(ValueError):
        encode_mp3_test("VOL", 31)
    with pytest.raises(ValueError):
        encode_mp3_test("PLAY", 0)
    with pytest.raises(ValueError):
        encode_mp3_test("PLAYVOL", 0)
    with pytest.raises(ValueError):
        encode_mp3_test("BAD")


def test_parse_profile():
    assert parse_line(b"PROFILE:LEGACY_2_SERVO_OPENSMART\n") == (
        "profile",
        "LEGACY_2_SERVO_OPENSMART",
        None,
    )


def test_parse_log():
    msg = parse_line(b"LOG:hello world\n")
    assert msg == ("log", None, "hello world")


def test_parse_bin_fullness():
    msg = parse_line(b"BIN:2:75\n")
    assert msg == ("bin", 2, 75)


def test_parse_rejects_invalid_bin_fullness():
    assert parse_line(b"BIN:0:75\n") is None
    assert parse_line(b"BIN:2:101\n") is None
    assert parse_line(b"BIN:2:not-a-number\n") is None


def test_parse_proximity_event():
    assert parse_line(b"PROX:O\n") == ("proximity", "O", None)
    assert parse_line(b"PROX:R\n") == ("proximity", "R", None)
    assert parse_line(b"PROX:I\n") == ("proximity", "I", None)
    assert parse_line(b"PROX:X\n") is None


def test_parse_audio_event():
    assert parse_line(b"AUDIO:O:2:sort\n") == (
        "audio",
        "O",
        {"track": 2, "source": "sort"},
    )
    assert parse_line(b"AUDIO:O:5:prox\n") == (
        "audio",
        "O",
        {"track": 5, "source": "prox"},
    )
    assert parse_line(b"AUDIO:MANUAL:7:manual\n") == (
        "audio",
        "MANUAL",
        {"track": 7, "source": "manual"},
    )


def test_parse_rejects_invalid_audio_event():
    assert parse_line(b"AUDIO:O:bad:prox\n") is None
    assert parse_line(b"AUDIO:O:5\n") is None


def test_parse_mp3_diagnostics():
    assert parse_line(b"MP3TX:7E 04 41 00 01 EF\n") == (
        "mp3",
        "tx",
        "7E 04 41 00 01 EF",
    )
    assert parse_line(b"MP3RX:7E 02 00 EF\n") == (
        "mp3",
        "rx",
        "7E 02 00 EF",
    )
    assert parse_line(b"MP3:READY\n") == ("mp3", "ready", None)
    assert parse_line(b"MP3:PROTO:open_smart_serial_mp3_a\n") == (
        "mp3",
        "proto",
        "open_smart_serial_mp3_a",
    )
    assert parse_line(b"MP3:VOL:30\n") == ("mp3", "vol", "30")
    assert parse_line(b"MP3:ERR:bad_track\n") == ("mp3", "error", "bad_track")


def test_parse_servo_home_diagnostics():
    assert parse_line(b"SERVO:HOME:90:88\n") == (
        "servo",
        "home",
        {"D6": 90, "D7": 88},
    )


def test_parse_unknown_returns_none():
    assert parse_line(b"random text\n") is None
