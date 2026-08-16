"""Tests for deadman_switch.debrief -- post-incident debrief generator."""

from __future__ import annotations

import pytest

from deadman_switch.debrief import (
    DebriefError, classify_outcome, render_debrief,
)
from deadman_switch.events import EventLog
from deadman_switch.journal import Journal


def _fired_log():
    log = EventLog()
    log.append("arm", {"ttl": 60}, at=1000.0)
    log.append("beat", at=1030.0)
    log.append("warn", {"age": 61}, at=1061.0)
    log.append("trip", {"age": 91}, at=1091.0)
    log.append("fire", at=1092.0)
    return log


def _rescued_log():
    log = EventLog()
    log.append("arm", at=1.0)
    log.append("warn", at=2.0)
    log.append("rescue", at=3.0)
    log.append("beat", at=3.0)
    return log


def test_classify_fired():
    outcome = classify_outcome(_fired_log())
    assert outcome["fired"] is True
    assert outcome["rescued"] is False
    assert outcome["beats"] == 1
    assert outcome["warnings"] == 1
    assert outcome["trips"] == 1


def test_classify_rescued():
    outcome = classify_outcome(_rescued_log())
    assert outcome["fired"] is False
    assert outcome["rescued"] is True


def test_render_debrief_sections():
    text = render_debrief(_fired_log(), switch_id="alpha")
    assert "# Debrief: alpha" in text
    assert "## Outcome" in text
    assert "Fired: **yes**" in text
    assert "## Timeline" in text
    assert "## Analysis" in text
    assert "root cause" in text


def test_render_debrief_with_journal():
    journal = Journal()
    journal.add(1000.0, "left home", ["travel"])
    text = render_debrief(_fired_log(), journal=journal)
    assert "## Operator journal" in text
    assert "left home" in text


def test_render_debrief_summary():
    text = render_debrief(_fired_log(), summary="Operator missed a flight.")
    assert "Operator missed a flight." in text


def test_render_debrief_empty_log_raises():
    with pytest.raises(DebriefError):
        render_debrief(EventLog())


def test_render_debrief_chain_intact():
    text = render_debrief(_fired_log())
    assert "Event chain intact: True" in text
