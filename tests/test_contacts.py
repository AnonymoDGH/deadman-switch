"""Tests for deadman_switch.contacts -- trusted contact roster."""

from __future__ import annotations

import pytest

from deadman_switch.contacts import Contact, ContactError, Roster


def _roster():
    return Roster([
        Contact("alice", "email:a@x", priority=1, clearance="full"),
        Contact("bob", "sms:+1", priority=2, clearance="alert-only"),
        Contact("carol", "signal:carol", priority=3, clearance="none"),
    ])


def test_contact_validation():
    with pytest.raises(ContactError):
        Contact("  ", "email")
    with pytest.raises(ContactError):
        Contact("a", "  ")
    with pytest.raises(ContactError):
        Contact("a", "email", clearance="top-secret")
    with pytest.raises(ContactError):
        Contact("a", "email", priority=-1)


def test_roster_add_duplicate():
    roster = _roster()
    with pytest.raises(ContactError):
        roster.add(Contact("alice", "other"))


def test_roster_get_and_remove():
    roster = _roster()
    assert roster.get("bob").channel == "sms:+1"
    roster.remove("bob")
    assert roster.names() == ["alice", "carol"]
    with pytest.raises(ContactError):
        roster.get("bob")


def test_notification_order():
    roster = _roster()
    order = [c.name for c in roster.notification_order()]
    assert order == ["alice", "bob", "carol"]


def test_primary():
    roster = _roster()
    assert roster.primary().name == "alice"
    assert Roster().primary() is None


def test_cleared_levels():
    roster = _roster()
    full = [c.name for c in roster.cleared("full")]
    assert full == ["alice"]
    alert = [c.name for c in roster.cleared("alert-only")]
    assert alert == ["alice", "bob"]
    everyone = [c.name for c in roster.cleared("none")]
    assert everyone == ["alice", "bob", "carol"]


def test_cleared_unknown_level():
    roster = _roster()
    with pytest.raises(ContactError):
        roster.cleared("bogus")


def test_rotate():
    roster = _roster()
    roster.rotate(1)
    assert roster.primary().name == "bob"
    roster.rotate(1)
    assert roster.primary().name == "carol"
    roster.rotate(1)
    assert roster.primary().name == "alice"


def test_rotate_empty():
    Roster().rotate(1)  # no error


def test_redundancy():
    roster = _roster()
    assert roster.redundancy_ok(required=2) is True
    assert roster.redundancy_ok(required=3) is False


def test_serialization_roundtrip():
    roster = _roster()
    restored = Roster.from_list(roster.to_list())
    assert restored.names() == roster.names()
    assert restored.get("alice").clearance == "full"
