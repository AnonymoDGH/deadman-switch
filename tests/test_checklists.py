"""Tests for deadman_switch.checklists -- pre-arm safety checklists."""

from __future__ import annotations

import pytest

from deadman_switch.checklists import (
    CHECKLISTS, Checklist, ChecklistError, ChecklistItem, get_checklist,
)


def test_library_has_three():
    assert sorted(CHECKLISTS) == ["pre-arm", "pre-release", "pre-travel"]


def test_get_checklist_fresh_copy():
    a = get_checklist("pre-arm")
    b = get_checklist("pre-arm")
    a.confirm("ttl")
    assert b.is_confirmed("ttl") is False  # independent copies


def test_get_unknown_raises():
    with pytest.raises(ChecklistError):
        get_checklist("bogus")


def test_item_validation():
    with pytest.raises(ChecklistError):
        ChecklistItem("  ", "prompt")
    with pytest.raises(ChecklistError):
        ChecklistItem("id", "  ")


def test_checklist_validation():
    with pytest.raises(ChecklistError):
        Checklist("  ", [ChecklistItem("a", "p")])
    with pytest.raises(ChecklistError):
        Checklist("x", [])
    with pytest.raises(ChecklistError):
        Checklist("x", [ChecklistItem("a", "p"), ChecklistItem("a", "q")])


def test_confirm_and_pending():
    checklist = get_checklist("pre-arm")
    checklist.confirm("ttl")
    assert checklist.is_confirmed("ttl") is True
    pending_ids = [item.item_id for item in checklist.pending()]
    assert "ttl" not in pending_ids


def test_confirm_unknown_raises():
    checklist = get_checklist("pre-arm")
    with pytest.raises(ChecklistError):
        checklist.confirm("nonexistent")


def test_unconfirm():
    checklist = get_checklist("pre-arm")
    checklist.confirm("ttl")
    checklist.unconfirm("ttl")
    assert checklist.is_confirmed("ttl") is False


def test_ready_requires_mandatory():
    checklist = get_checklist("pre-arm")
    assert checklist.ready() is False
    for item in checklist.items:
        if item.mandatory:
            checklist.confirm(item.item_id)
    assert checklist.ready() is True
    # Optional item still pending does not block readiness.
    assert checklist.pending()  # heartbeat-path still pending


def test_progress():
    checklist = get_checklist("pre-arm")
    checklist.confirm("ttl")
    progress = checklist.progress()
    assert progress["confirmed"] == 1
    assert progress["total"] == len(checklist.items)
    assert progress["ready"] is False


def test_render_marks():
    checklist = get_checklist("pre-arm")
    checklist.confirm("ttl")
    text = checklist.render()
    assert "# pre-arm" in text
    assert "[x]" in text
    assert "[ ]" in text
    assert "(optional)" in text
