"""Tests for deadman_switch.report -- human-readable reports."""

from __future__ import annotations

from deadman_switch.events import EventLog
from deadman_switch.report import (
    format_timestamp, postmortem_report, status_report, timeline_report,
)
from deadman_switch.state import State


def _log():
    log = EventLog()
    log.append("arm", {"ttl": 60}, at=1000.0)
    log.append("beat", at=1030.0)
    log.append("warn", {"age": 61}, at=1061.0)
    log.append("trip", {"age": 91}, at=1091.0)
    log.append("fire", at=1092.0)
    return log


def test_format_timestamp():
    text = format_timestamp(0.0)
    assert "1970-01-01" in text
    assert "UTC" in text


def test_status_armed():
    text = status_report(State.ARMED, age=10, slack=50, ttl_seconds=60)
    assert "ALIVE" in text
    assert "10s ago" in text
    assert "50s" in text


def test_status_warning():
    text = status_report(State.WARNING, age=70, slack=20,
                         ttl_seconds=60, grace_seconds=30)
    assert "WARNING" in text
    assert "grace" in text


def test_status_tripped():
    text = status_report(State.TRIPPED, age=100, slack=0, ttl_seconds=60)
    assert "TRIPPED" in text


def test_status_disarmed():
    text = status_report(State.DISARMED, age=None, slack=None, ttl_seconds=60)
    assert "disarmed" in text


def test_status_fired():
    text = status_report(State.FIRED, age=None, slack=None, ttl_seconds=60)
    assert "FIRED" in text


def test_timeline_report():
    text = timeline_report(_log())
    assert "EVENT TIMELINE" in text
    assert "arm" in text
    assert "fire" in text
    assert "chain intact: True" in text


def test_timeline_empty():
    text = timeline_report(EventLog())
    assert "no events" in text


def test_postmortem_fired():
    log = _log()
    text = postmortem_report(log, State.FIRED,
                             payload_result={"ok": True, "detail": "wrote file"})
    assert "POST-MORTEM" in text
    assert "fired:        yes" in text
    assert "payload ok:   yes" in text
    assert "beats:        1" in text


def test_postmortem_not_fired():
    log = EventLog()
    log.append("arm", at=1.0)
    log.append("beat", at=2.0)
    text = postmortem_report(log, State.ARMED)
    assert "fired:        no" in text


def test_postmortem_payload_failure():
    log = _log()
    text = postmortem_report(log, State.FIRED,
                             payload_result={"ok": False, "detail": "boom"})
    assert "payload ok:   NO" in text
