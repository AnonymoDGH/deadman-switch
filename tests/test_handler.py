"""Tests for deadman_switch.handler -- mission-control orchestrator."""

from __future__ import annotations

import pytest

from deadman_switch.channels import FileChannel
from deadman_switch.clock import FixedClock
from deadman_switch.contacts import Contact, Roster
from deadman_switch.dispatcher import Dispatcher
from deadman_switch.engine import SwitchConfig
from deadman_switch.handler import Handler, HandlerError
from deadman_switch.state import State
from deadman_switch.store import SwitchStore


def _handler(tmp_path, grace=30.0):
    clock = FixedClock(start=0.0)
    config = SwitchConfig(ttl_seconds=60, grace_seconds=grace)
    roster = Roster([
        Contact("alice", "file:alice", priority=1, clearance="full"),
        Contact("bob", "file:bob", priority=2, clearance="alert-only"),
    ])
    dispatcher = Dispatcher(roster)
    dispatcher.register_channel("file", FileChannel(tmp_path / "alerts.jsonl"))
    store = SwitchStore(tmp_path / "store")
    return Handler("switch-1", config, clock=clock, store=store,
                   roster=roster, dispatcher=dispatcher,
                   payload={"type": "notify", "label": "it"}), clock


def test_handler_validation():
    with pytest.raises(HandlerError):
        Handler("  ", SwitchConfig(ttl_seconds=60))


def test_arm_and_beat(tmp_path):
    handler, clock = _handler(tmp_path)
    handler.arm(note="starting mission")
    assert handler.state == State.ARMED
    handler.beat(note="all good")
    assert len(handler.journal) == 2


def test_tick_dispatches_on_warning(tmp_path):
    handler, clock = _handler(tmp_path)
    handler.arm()
    clock.advance(61)
    state = handler.tick()
    assert state == State.WARNING
    assert handler.dispatched_levels == ["warn"]
    # Both contacts cleared for alert-only get notified.
    assert (tmp_path / "alerts.jsonl").exists()


def test_dispatch_not_duplicated(tmp_path):
    handler, clock = _handler(tmp_path)
    handler.arm()
    clock.advance(61)
    handler.tick()  # WARNING
    clock.advance(1)
    handler.tick()  # still WARNING
    assert handler.dispatched_levels == ["warn"]


def test_full_escalation(tmp_path):
    handler, clock = _handler(tmp_path)
    handler.arm()
    clock.advance(61)
    handler.tick()   # WARNING
    clock.advance(31)
    handler.tick()   # TRIPPED
    clock.advance(1)
    handler.tick()   # FIRED
    assert handler.state == State.FIRED
    assert handler.dispatched_levels == ["warn", "trip", "fire"]


def test_beat_rescues_and_stops_escalation(tmp_path):
    handler, clock = _handler(tmp_path)
    handler.arm()
    clock.advance(61)
    handler.tick()   # WARNING
    handler.beat(note="rescued")
    assert handler.state == State.ARMED
    clock.advance(10)
    handler.tick()
    assert handler.state == State.ARMED
    assert handler.dispatched_levels == ["warn"]


def test_cancel(tmp_path):
    handler, clock = _handler(tmp_path)
    handler.arm()
    clock.advance(61)
    handler.tick()   # WARNING
    clock.advance(31)
    handler.tick()   # TRIPPED
    handler.cancel()
    assert handler.state == State.DISARMED


def test_persistence(tmp_path):
    handler, clock = _handler(tmp_path)
    handler.arm()
    assert (tmp_path / "store" / "switch.json").exists()
    assert (tmp_path / "store" / "events.jsonl").exists()


def test_summary(tmp_path):
    handler, clock = _handler(tmp_path)
    handler.arm(note="go")
    handler.beat()
    summary = handler.summary()
    assert summary["switch_id"] == "switch-1"
    assert summary["state"] == State.ARMED
    assert summary["beats"] == 1
    assert summary["journal_entries"] == 1
    assert summary["contacts"] == 2
