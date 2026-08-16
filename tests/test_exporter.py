"""Tests for deadman_switch.exporter -- portable state exports."""

from __future__ import annotations

import json

from deadman_switch.events import EventLog
from deadman_switch.exporter import (
    export_cheat_sheet, export_json, export_markdown,
)
from deadman_switch.journal import Journal
from deadman_switch.state import State


def _config():
    return {
        "ttl_seconds": 3600,
        "grace_seconds": 600,
        "payload": {"type": "email", "to": "a@b.c", "smtp_pass": "secret"},
    }


def _log():
    log = EventLog()
    log.append("arm", {"ttl": 3600}, at=1000.0)
    log.append("beat", at=1030.0)
    return log


def _journal():
    j = Journal()
    j.add(1000.0, "left home", ["travel"])
    j.add(1030.0, "safe")
    return j


def test_export_json_shape():
    text = export_json(State.ARMED, _config(), _log(), _journal())
    data = json.loads(text)
    assert data["state"] == State.ARMED
    assert data["chain_intact"] is True
    assert len(data["events"]) == 2
    assert len(data["journal"]) == 2


def test_export_json_no_journal():
    data = json.loads(export_json(State.ARMED, _config(), _log()))
    assert "journal" not in data


def test_export_json_redacted():
    text = export_json(State.ARMED, _config(), _log(), redact=True)
    data = json.loads(text)
    assert data["config"]["payload"]["smtp_pass"] == "[redacted]"


def test_export_markdown_sections():
    text = export_markdown(State.ARMED, _config(), _log(), _journal(),
                           switch_id="alpha")
    assert "# Switch briefing: alpha" in text
    assert "**State:** armed" in text
    assert "## Events" in text
    assert "## Journal" in text
    assert "left home" in text


def test_export_markdown_empty_log():
    text = export_markdown(State.DISARMED, _config(), EventLog())
    assert "_No events recorded._" in text


def test_export_markdown_event_detail():
    text = export_markdown(State.ARMED, _config(), _log())
    assert "ttl=3600" in text


def test_export_cheat_sheet():
    text = export_cheat_sheet(State.ARMED, _config(), switch_id="alpha")
    assert "SWITCH alpha" in text
    assert "ttl 3600s" in text
    assert "dms heartbeat" in text
    assert "signed token" in text


def test_export_cheat_sheet_defaults():
    text = export_cheat_sheet(State.ARMED, {})
    assert "payload print" in text
