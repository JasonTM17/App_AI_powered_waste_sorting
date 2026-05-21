import pytest

from app.core.uart_protocol import encode_sort, parse_line


def test_encode_sort_basic():
    assert encode_sort("S", 0.92) == b"SORT:S:0.92\n"


def test_encode_sort_clamps_conf():
    assert encode_sort("P", 1.5) == b"SORT:P:1.00\n"
    assert encode_sort("P", -0.1) == b"SORT:P:0.00\n"


def test_encode_sort_rejects_bad_command():
    with pytest.raises(ValueError):
        encode_sort("", 0.5)
    with pytest.raises(ValueError):
        encode_sort("AB", 0.5)


def test_parse_ack():
    msg = parse_line(b"ACK:S\n")
    assert msg == ("ack", "S", None)


def test_parse_nack_with_reason():
    msg = parse_line(b"NACK:S:busy\n")
    assert msg == ("nack", "S", "busy")


def test_parse_pong():
    msg = parse_line(b"PONG\n")
    assert msg == ("pong", None, None)


def test_parse_log():
    msg = parse_line(b"LOG:hello world\n")
    assert msg == ("log", None, "hello world")


def test_parse_unknown_returns_none():
    assert parse_line(b"random text\n") is None
