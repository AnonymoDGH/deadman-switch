"""Tests for deadman_switch.watchdog -- multi-switch manager."""

from __future__ import annotations

import pytest

from deadman_switch.clock import FixedClock
from deadman_switch.engine import SwitchConfig
from deadman_switch.state import State
from deadman_switch.watchdog import Watchdog, WatchdogError


def _watchdog():
    wd = Watchdog(clock=FixedClock(start=0.0))
    wd.add("alpha", SwitchConfig(ttl_seconds=60))
    wd.add("beta", SwitchConfig(ttl_seconds=120))
    return wd


def test_add_and_names():
    wd = _watchdog()
    assert wd.names() == ["alpha", "beta"]
    assert len(wd) == 2


def test_add_duplicate_rejected():
    wd = _watchdog()
    with pytest.raises(WatchdogError):
        wd.add("alpha", SwitchConfig(ttl_seconds=60))


def test_add_empty_name_rejected():
    wd = Watchdog()
    with pytest.raises(WatchdogError):
        wd.add("  ", SwitchConfig(ttl_seconds=60))


def test_get_and_remove():
    wd = _watchdog()
    assert wd.get("alpha").state == State.DISARMED
    wd.remove("alpha")
    assert wd.names() == ["beta"]
    with pytest.raises(WatchdogError):
        wd.get("alpha")


def test_arm_all():
    wd = _watchdog()
    wd.arm_all()
    assert wd.states() == {"alpha": State.ARMED, "beta": State.ARMED}


def test_tick_all_keeps_alive_with_beats():
    wd = _watchdog()
    wd.arm_all()
    wd.clock.advance(30)
    wd.beat_all()
    states = wd.tick_all()
    assert states["alpha"] == State.ARMED
    assert states["beta"] == State.ARMED


def test_silence_fires_only_short_ttl():
    wd = _watchdog()
    wd.arm_all()
    wd.clock.advance(70)  # past alpha's 60s TTL, under beta's 120s
    states = wd.tick_all()
    assert states["alpha"] == State.FIRED
    assert states["beta"] == State.ARMED
    assert wd.fired() == ["alpha"]


def test_beat_rescues_one_switch():
    wd = _watchdog()
    wd.arm_all()
    wd.clock.advance(70)
    wd.beat("alpha")  # rescue alpha just in time
    states = wd.tick_all()
    assert states["alpha"] == State.ARMED
    assert wd.fired() == []


def test_live_and_summary():
    wd = _watchdog()
    wd.arm_all()
    wd.clock.advance(70)
    wd.tick_all()
    assert wd.live() == ["beta"]
    summary = wd.summary()
    assert summary[State.FIRED] == 1
    assert summary[State.ARMED] == 1


def test_shared_clock():
    clock = FixedClock(start=0.0)
    wd = Watchdog(clock=clock)
    wd.add("x", SwitchConfig(ttl_seconds=60))
    assert wd.clock is clock
    assert wd.get("x").last_beat is None
