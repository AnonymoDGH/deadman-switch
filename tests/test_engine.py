"""Tests for deadman_switch.engine -- the switch engine."""

from __future__ import annotations

import pytest

from deadman_switch.clock import FixedClock
from deadman_switch.engine import Switch, SwitchConfig, SwitchError
from deadman_switch.state import State


def _switch(ttl=60, grace=0, on_fire=None):
    clock = FixedClock(start=1000.0)
    config = SwitchConfig(ttl_seconds=ttl, grace_seconds=grace)
    return Switch(config, clock=clock, on_fire=on_fire), clock


def test_config_validation():
    with pytest.raises(SwitchError):
        SwitchConfig(ttl_seconds=0)
    with pytest.raises(SwitchError):
        SwitchConfig(ttl_seconds=60, grace_seconds=-1)


def test_arm_sets_armed_and_beats():
    sw, clock = _switch()
    sw.arm()
    assert sw.state == State.ARMED
    assert sw.last_beat == clock.now()


def test_no_fire_within_ttl():
    sw, clock = _switch(ttl=60)
    sw.arm()
    clock.advance(30)
    assert sw.tick() == State.ARMED


def test_fire_after_ttl_no_grace():
    fired = []
    sw, clock = _switch(ttl=60, on_fire=lambda: fired.append(1))
    sw.arm()
    clock.advance(61)
    assert sw.tick() == State.FIRED
    assert fired == [1]


def test_fire_only_once():
    fired = []
    sw, clock = _switch(ttl=60, on_fire=lambda: fired.append(1))
    sw.arm()
    clock.advance(61)
    sw.tick()
    clock.advance(100)
    sw.tick()
    assert fired == [1]


def test_grace_period_warns_then_trips():
    sw, clock = _switch(ttl=60, grace=30)
    sw.arm()
    clock.advance(61)
    assert sw.tick() == State.WARNING
    clock.advance(15)
    assert sw.tick() == State.WARNING  # still in grace
    clock.advance(20)
    assert sw.tick() == State.TRIPPED


def test_beat_rescues_from_warning():
    sw, clock = _switch(ttl=60, grace=30)
    sw.arm()
    clock.advance(61)
    sw.tick()  # -> WARNING
    sw.beat()
    assert sw.state == State.ARMED
    clock.advance(30)
    assert sw.tick() == State.ARMED


def test_beat_rescues_from_tripped():
    sw, clock = _switch(ttl=60, grace=30)
    sw.arm()
    clock.advance(61)
    sw.tick()   # WARNING
    clock.advance(31)
    sw.tick()   # TRIPPED
    sw.beat()
    assert sw.state == State.ARMED


def test_cancel_from_tripped():
    sw, clock = _switch(ttl=60, grace=30)
    sw.arm()
    clock.advance(61)
    sw.tick()
    clock.advance(31)
    sw.tick()   # TRIPPED
    sw.cancel()
    assert sw.state == State.DISARMED


def test_age_and_slack():
    sw, clock = _switch(ttl=60)
    sw.arm()
    clock.advance(20)
    assert sw.age() == 20
    assert sw.slack() == 40


def test_slack_none_before_beat():
    sw, clock = _switch()
    assert sw.age() is None
    assert sw.slack() is None


def test_event_log_records_lifecycle():
    sw, clock = _switch(ttl=60)
    sw.arm()
    clock.advance(61)
    sw.tick()
    kinds = sw.log.kinds()
    assert "arm" in kinds
    assert "trip" in kinds
    assert "fire" in kinds
    assert sw.log.verify() is True


def test_heartbeat_file_touched(tmp_path):
    hb = tmp_path / "hb"
    clock = FixedClock()
    config = SwitchConfig(ttl_seconds=60, heartbeat_path=hb)
    sw = Switch(config, clock=clock)
    sw.arm()
    assert hb.exists()


def test_disarm_stops_ticking():
    sw, clock = _switch(ttl=60)
    sw.arm()
    sw.disarm()
    clock.advance(999)
    assert sw.tick() == State.DISARMED

def test_engine_executes_payload_action(tmp_path):
    from deadman_switch.engine import Switch, SwitchConfig
    from deadman_switch.clock import FixedClock
    from deadman_switch.state import State
    target = tmp_path / "fired.txt"
    clock = FixedClock()
    config = SwitchConfig(ttl_seconds=60)
    sw = Switch(config, clock=clock,
                payload={"type": "file", "path": str(target), "message": "gone"})
    sw.arm()
    clock.advance(61)
    sw.tick()
    assert sw.state == State.FIRED
    assert target.exists()
    assert sw.last_result is not None and sw.last_result.ok
    assert "payload" in sw.log.kinds()

def test_engine_save_load_roundtrip(tmp_path):
    from deadman_switch.engine import Switch, SwitchConfig
    from deadman_switch.clock import FixedClock
    from deadman_switch.state import State
    from deadman_switch.store import SwitchStore
    clock = FixedClock(start=1000.0)
    config = SwitchConfig(ttl_seconds=60, grace_seconds=30)
    sw = Switch(config, clock=clock)
    sw.arm()
    clock.advance(61)
    sw.tick()  # -> WARNING
    store = SwitchStore(tmp_path / "store")
    sw.save(store)

    restored = Switch.load(store, clock=FixedClock(start=2000.0))
    assert restored.state == State.WARNING
    assert restored.last_beat == sw.last_beat
    assert restored.log.verify() is True
    assert len(restored.log) == len(sw.log)


def test_engine_load_fired_state(tmp_path):
    from deadman_switch.engine import Switch, SwitchConfig
    from deadman_switch.clock import FixedClock
    from deadman_switch.state import State
    from deadman_switch.store import SwitchStore
    clock = FixedClock(start=1000.0)
    config = SwitchConfig(ttl_seconds=60)  # no grace
    sw = Switch(config, clock=clock)
    sw.arm()
    clock.advance(61)
    sw.tick()  # -> FIRED
    assert sw.state == State.FIRED
    store = SwitchStore(tmp_path / "store")
    sw.save(store)

    restored = Switch.load(store, clock=FixedClock(start=2000.0))
    assert restored.state == State.FIRED
