"""Tests for deadman_switch.dispatcher -- alert routing to contacts."""

from __future__ import annotations

import pytest

from deadman_switch.channels import FileChannel, SendResult
from deadman_switch.contacts import Contact, Roster
from deadman_switch.dispatcher import Dispatcher, DispatchError


def _roster():
    return Roster([
        Contact("alice", "file:alice", priority=1, clearance="full"),
        Contact("bob", "file:bob", priority=2, clearance="alert-only"),
        Contact("carol", "sms:carol", priority=3, clearance="none"),
    ])


def _dispatcher(tmp_path):
    dispatcher = Dispatcher(_roster())
    dispatcher.register_channel("file", FileChannel(tmp_path / "alerts.jsonl"))
    return dispatcher


def test_register_channel_validation(tmp_path):
    dispatcher = Dispatcher(_roster())
    with pytest.raises(DispatchError):
        dispatcher.register_channel("  ", FileChannel(tmp_path / "x"))


def test_render_message(tmp_path):
    dispatcher = _dispatcher(tmp_path)
    contact = Contact("alice", "file:alice")
    message = dispatcher.render_message("fire", contact, "switch-1")
    assert isinstance(message, str)
    assert "switch-1" in message
    assert "alice" in message
    assert "FIRED" in message


def test_render_message_unknown_level(tmp_path):
    dispatcher = _dispatcher(tmp_path)
    contact = Contact("alice", "file:alice")
    with pytest.raises(DispatchError):
        dispatcher.render_message("bogus", contact, "s")


def test_fire_notifies_everyone(tmp_path):
    dispatcher = _dispatcher(tmp_path)
    results = dispatcher.dispatch("fire", "switch-1")
    # alice and bob have file channels; carol has sms (unregistered).
    assert len(results) == 3
    assert sorted(dispatcher.notified("fire")) == ["alice", "bob"]


def test_warn_notifies_alert_only_and_above(tmp_path):
    dispatcher = _dispatcher(tmp_path)
    dispatcher.dispatch("warn", "switch-1")
    assert sorted(dispatcher.notified("warn")) == ["alice", "bob"]


def test_trip_notifies_full_only(tmp_path):
    dispatcher = _dispatcher(tmp_path)
    dispatcher.dispatch("trip", "switch-1")
    assert dispatcher.notified("trip") == ["alice"]


def test_missing_channel_recorded_as_failure(tmp_path):
    dispatcher = _dispatcher(tmp_path)
    results = dispatcher.dispatch("fire", "switch-1")
    failed = [r for r in results if not r.ok]
    assert len(failed) == 1
    assert "no channel" in failed[0].detail


def test_dispatch_unknown_level(tmp_path):
    dispatcher = _dispatcher(tmp_path)
    with pytest.raises(DispatchError):
        dispatcher.dispatch("bogus", "switch-1")


def test_log_records_attempts(tmp_path):
    dispatcher = _dispatcher(tmp_path)
    dispatcher.dispatch("warn", "switch-1")
    log = dispatcher.log
    assert len(log) == 2
    assert all(entry["level"] == "warn" for entry in log)


def test_messages_written_to_channel(tmp_path):
    dispatcher = _dispatcher(tmp_path)
    dispatcher.dispatch("fire", "switch-1")
    text = (tmp_path / "alerts.jsonl").read_text(encoding="utf-8")
    assert "switch-1" in text
