"""Tests for deadman_switch.events -- hash-chained event log."""

from __future__ import annotations

import pytest

from deadman_switch.events import (
    GENESIS_HASH, Event, EventLog, EventLogError,
)


def test_empty_log_head_is_genesis():
    log = EventLog()
    assert log.head_hash == GENESIS_HASH
    assert len(log) == 0


def test_append_links_to_previous():
    log = EventLog()
    first = log.append("arm", at=1.0)
    assert first.prev_hash == GENESIS_HASH
    second = log.append("beat", at=2.0)
    assert second.prev_hash == first.hash


def test_verify_clean_chain():
    log = EventLog()
    log.append("arm", {"ttl": 60}, at=1.0)
    log.append("beat", at=2.0)
    log.append("warn", at=3.0)
    assert log.verify() is True
    assert log.first_broken() is None


def test_tampered_detail_detected():
    log = EventLog()
    log.append("arm", {"ttl": 60}, at=1.0)
    log.append("beat", at=2.0)
    # Tamper with the first event's detail.
    log._events[0].detail = {"ttl": 9999}
    assert log.verify() is False
    assert log.first_broken() == 0


def test_deleted_event_detected():
    log = EventLog()
    log.append("arm", at=1.0)
    log.append("beat", at=2.0)
    log.append("warn", at=3.0)
    del log._events[1]  # remove the middle event
    assert log.verify() is False


def test_kinds_histogram():
    log = EventLog()
    log.append("beat")
    log.append("beat")
    log.append("warn")
    assert log.kinds() == {"beat": 2, "warn": 1}


def test_roundtrip_text():
    log = EventLog()
    log.append("arm", {"ttl": 60}, at=1.0)
    log.append("fire", at=2.0)
    text = log.to_text()
    restored = EventLog.from_text(text)
    assert len(restored) == 2
    assert restored.verify() is True
    assert restored.head_hash == log.head_hash


def test_from_text_corrupt_raises():
    with pytest.raises(EventLogError):
        EventLog.from_text("{not json")


def test_event_to_dict_roundtrip():
    log = EventLog()
    event = log.append("arm", {"ttl": 60}, at=1.0)
    restored = Event.from_dict(event.to_dict())
    assert restored.hash == event.hash
    assert restored.kind == event.kind
