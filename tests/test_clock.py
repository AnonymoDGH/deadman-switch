"""Tests for deadman_switch.clock -- deterministic clocks."""

from __future__ import annotations

import time

import pytest

from deadman_switch.clock import FixedClock, WallClock, default_clock


def test_wall_clock_advances():
    clock = WallClock()
    a = clock.now()
    time.sleep(0.01)
    b = clock.now()
    assert b > a


def test_fixed_clock_starts_at_given_time():
    clock = FixedClock(start=42.0)
    assert clock.now() == 42.0


def test_fixed_clock_advance():
    clock = FixedClock(start=0.0)
    new = clock.advance(10.5)
    assert new == 10.5
    assert clock.now() == 10.5


def test_fixed_clock_advance_negative_rejected():
    clock = FixedClock()
    with pytest.raises(ValueError):
        clock.advance(-1)


def test_fixed_clock_set():
    clock = FixedClock()
    clock.set(999.0)
    assert clock.now() == 999.0


def test_fixed_clock_sleep_fast_forwards():
    clock = FixedClock(start=0.0)
    start = time.time()
    clock.sleep(3600)  # an hour, instantly
    assert clock.now() == 3600.0
    assert time.time() - start < 1.0


def test_default_clock_is_wall():
    assert isinstance(default_clock(), WallClock)
