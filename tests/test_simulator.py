"""Tests for deadman_switch.simulator -- scenario simulation."""

from __future__ import annotations

import pytest

from deadman_switch.engine import SwitchConfig
from deadman_switch.simulator import (
    Scenario, SimError, missed_beat, regular_beats, run_scenario,
    silence_after,
)
from deadman_switch.state import State


def test_scenario_validation():
    with pytest.raises(SimError):
        Scenario(0, [])
    with pytest.raises(SimError):
        Scenario(100, [150])  # beat beyond total


def test_regular_beats_builder():
    s = regular_beats(100, 25)
    assert s.beats == [25, 50, 75, 100]


def test_regular_beats_bad_interval():
    with pytest.raises(SimError):
        regular_beats(100, 0)


def test_silence_after_builder():
    s = silence_after(100, 25, silence_from=50)
    assert s.beats == [25]  # only beats before 50


def test_missed_beat_builder():
    s = missed_beat(100, 25, missed_index=1)
    assert s.beats == [25, 75, 100]  # 50 is missing


def test_healthy_operator_never_fires():
    config = SwitchConfig(ttl_seconds=60)
    scenario = regular_beats(300, interval=30)
    result = run_scenario(config, scenario, tick_interval=10)
    assert result.fired is False
    assert result.final_state == State.ARMED


def test_silence_fires():
    config = SwitchConfig(ttl_seconds=60)
    scenario = silence_after(300, interval=30, silence_from=60)
    result = run_scenario(config, scenario, tick_interval=10)
    assert result.fired is True
    assert result.final_state == State.FIRED
    assert result.fired_at is not None
    # Fires sometime after the 60s TTL past the last beat.
    assert result.fired_at > 60


def test_grace_period_delays_fire():
    no_grace = SwitchConfig(ttl_seconds=60)
    with_grace = SwitchConfig(ttl_seconds=60, grace_seconds=60)
    scenario = silence_after(400, interval=30, silence_from=60)
    r1 = run_scenario(no_grace, scenario, tick_interval=10)
    r2 = run_scenario(with_grace, scenario, tick_interval=10)
    assert r1.fired and r2.fired
    assert r2.fired_at > r1.fired_at


def test_missed_single_beat_survives():
    # TTL 60, beat every 30; missing one beat leaves a 60s gap == TTL, not >.
    config = SwitchConfig(ttl_seconds=60)
    scenario = missed_beat(300, interval=30, missed_index=2)
    result = run_scenario(config, scenario, tick_interval=5)
    assert result.fired is False


def test_state_at():
    config = SwitchConfig(ttl_seconds=60)
    scenario = silence_after(300, interval=30, silence_from=60)
    result = run_scenario(config, scenario, tick_interval=10)
    assert result.state_at(0) == State.ARMED
    assert result.state_at(result.fired_at) == State.FIRED


def test_timeline_records_events():
    config = SwitchConfig(ttl_seconds=60)
    scenario = regular_beats(100, interval=30)
    result = run_scenario(config, scenario, tick_interval=10)
    events = {step["event"] for step in result.timeline}
    assert "arm" in events
    assert "beat" in events
    assert "tick" in events


def test_bad_tick_interval():
    config = SwitchConfig(ttl_seconds=60)
    with pytest.raises(SimError):
        run_scenario(config, regular_beats(100, 30), tick_interval=0)
