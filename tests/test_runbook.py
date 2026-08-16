"""Tests for deadman_switch.runbook -- handler runbook generation."""

from __future__ import annotations

from deadman_switch.runbook import (
    emergency_section, render_runbook, state_table,
)


def _config():
    return {
        "ttl_seconds": 3600,
        "grace_seconds": 1800,
        "payload": {"type": "email", "to": "a@b.c", "subject": "s"},
    }


def test_state_table_lists_all_states():
    text = state_table()
    for state in ("DISARMED", "ARMED", "WARNING", "TRIPPED", "FIRED"):
        assert state in text
    assert "| State |" in text


def test_emergency_section_with_contacts():
    contacts = [{"name": "alice", "channel": "email:a@x",
                 "clearance": "full"}]
    text = emergency_section(contacts)
    assert "alice" in text
    assert "email:a@x" in text
    assert "full" in text


def test_emergency_section_empty():
    text = emergency_section([])
    assert "No contacts" in text


def test_render_runbook_parameters():
    text = render_runbook(_config())
    assert "TTL: **3600s**" in text
    assert "Grace: **1800s**" in text
    assert "Payload: **email**" in text


def test_render_runbook_no_grace():
    config = _config()
    config["grace_seconds"] = 0
    text = render_runbook(config)
    assert "Grace: none" in text


def test_render_runbook_beat_schedule():
    text = render_runbook(_config())
    assert "Beat every **1800s**" in text  # 0.5 * 3600
    assert "Suggested cron" in text


def test_render_runbook_sections():
    text = render_runbook(_config())
    assert "## If the switch WARNS" in text
    assert "## If the switch TRIPS" in text
    assert "## After a fire" in text
    assert "duress code" in text


def test_render_runbook_deterministic():
    assert render_runbook(_config()) == render_runbook(_config())


def test_render_runbook_operator_name():
    text = render_runbook(_config(), operator="Agent K")
    assert "Operator: Agent K" in text


def test_render_runbook_contacts_embedded():
    contacts = [{"name": "bob", "channel": "sms:+1"}]
    text = render_runbook(_config(), contacts=contacts)
    assert "bob" in text
    assert "sms:+1" in text
