"""Tests for deadman_switch.timefmt -- time formatting and parsing."""

from __future__ import annotations

import pytest

from deadman_switch.timefmt import (
    TimeFormatError, countdown, format_duration, parse_duration,
    relative_time,
)


def test_format_duration_zero():
    assert format_duration(0) == "0s"


def test_format_duration_seconds():
    assert format_duration(45) == "45s"


def test_format_duration_minutes():
    assert format_duration(9000) == "2h 30m"


def test_format_duration_days():
    assert format_duration(90061) == "1d 1h 1m 1s"


def test_format_duration_negative():
    with pytest.raises(TimeFormatError):
        format_duration(-1)


def test_parse_duration_bare_number():
    assert parse_duration("90") == 90.0


def test_parse_duration_units():
    assert parse_duration("2h30m") == 9000.0
    assert parse_duration("1d") == 86400.0
    assert parse_duration("90s") == 90.0


def test_parse_duration_case_insensitive():
    assert parse_duration("2H30M") == 9000.0


def test_parse_duration_fractional():
    assert parse_duration("1.5h") == 5400.0


def test_parse_duration_empty():
    with pytest.raises(TimeFormatError):
        parse_duration("")
    with pytest.raises(TimeFormatError):
        parse_duration("   ")


def test_parse_duration_repeated_unit():
    with pytest.raises(TimeFormatError):
        parse_duration("1h1h")


def test_parse_duration_garbage():
    with pytest.raises(TimeFormatError):
        parse_duration("2h x")
    with pytest.raises(TimeFormatError):
        parse_duration("abc")


def test_parse_duration_zero():
    with pytest.raises(TimeFormatError):
        parse_duration("0s")


def test_relative_time_past_and_future():
    assert relative_time(120) == "2m ago"
    assert relative_time(-3600) == "in 1h"


def test_countdown_live():
    assert countdown(9000, "armed") == "2h 30m of slack left."


def test_countdown_exhausted():
    assert "exhausted" in countdown(0, "armed")


def test_countdown_fired():
    assert "FIRED" in countdown(None, "fired")


def test_countdown_disarmed():
    assert "disarmed" in countdown(None, "disarmed")


def test_countdown_unknown():
    assert "unknown" in countdown(None, "armed")
