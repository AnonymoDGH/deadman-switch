"""Tests for deadman_switch.state -- lifecycle state machine."""

from __future__ import annotations

import pytest

from deadman_switch.clock import FixedClock
from deadman_switch.state import State, StateError, SwitchStateMachine


def _armed():
    sm = SwitchStateMachine(clock=FixedClock())
    sm.arm()
    return sm


def test_starts_disarmed():
    sm = SwitchStateMachine()
    assert sm.state == State.DISARMED
    assert not sm.is_live


def test_arm():
    sm = _armed()
    assert sm.state == State.ARMED
    assert sm.is_live


def test_full_path_to_fired():
    sm = _armed()
    sm.warn()
    assert sm.state == State.WARNING
    sm.trip()
    assert sm.state == State.TRIPPED
    sm.fire()
    assert sm.state == State.FIRED
    assert sm.is_terminal


def test_beat_rescues_from_warning():
    sm = _armed()
    sm.warn()
    sm.beat()
    assert sm.state == State.ARMED


def test_beat_rescues_from_tripped():
    sm = _armed()
    sm.warn()
    sm.trip()
    sm.beat()
    assert sm.state == State.ARMED


def test_cancel_from_tripped():
    sm = _armed()
    sm.warn()
    sm.trip()
    sm.cancel()
    assert sm.state == State.DISARMED


def test_disarm_from_armed():
    sm = _armed()
    sm.disarm()
    assert sm.state == State.DISARMED


def test_invalid_transition_raises():
    sm = SwitchStateMachine()
    with pytest.raises(StateError):
        sm.fire()  # cannot fire from disarmed


def test_fired_is_terminal():
    sm = _armed()
    sm.warn()
    sm.trip()
    sm.fire()
    with pytest.raises(StateError):
        sm.beat()


def test_history_recorded():
    sm = _armed()
    sm.warn()
    sm.beat()
    kinds = [(t.from_state, t.to_state) for t in sm.history]
    assert kinds == [
        (State.DISARMED, State.ARMED),
        (State.ARMED, State.WARNING),
        (State.WARNING, State.ARMED),
    ]


def test_can():
    sm = _armed()
    assert sm.can(State.WARNING, "silence")
    assert not sm.can(State.FIRED, "fire")


def test_transition_timestamped():
    clock = FixedClock(start=100.0)
    sm = SwitchStateMachine(clock=clock)
    sm.arm()
    clock.advance(50)
    sm.warn()
    assert sm.history[0].at == 100.0
    assert sm.history[1].at == 150.0
