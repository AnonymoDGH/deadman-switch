"""Tests for deadman_switch.legacy -- digital legacy release planner."""

from __future__ import annotations

import pytest

from deadman_switch.legacy import LegacyError, LegacyPlan, ReleaseStage


def _plan():
    return LegacyPlan([
        ReleaseStage("immediate", ["emergency contacts", "final message"]),
        ReleaseStage("accounts", ["email credentials", "bank access"],
                     delay_seconds=3600),
        ReleaseStage("archive", ["photo archive", "journal"],
                     delay_seconds=86400, requires_ack="accounts"),
    ])


def test_stage_validation():
    with pytest.raises(LegacyError):
        ReleaseStage("  ", ["item"])
    with pytest.raises(LegacyError):
        ReleaseStage("x", [])
    with pytest.raises(LegacyError):
        ReleaseStage("x", ["item"], delay_seconds=-1)


def test_plan_validation():
    with pytest.raises(LegacyError):
        LegacyPlan([])
    with pytest.raises(LegacyError):
        LegacyPlan([ReleaseStage("a", ["x"]), ReleaseStage("a", ["y"])])


def test_plan_requires_known_stage():
    with pytest.raises(LegacyError):
        LegacyPlan([ReleaseStage("a", ["x"], requires_ack="ghost")])


def test_plan_requires_earlier_stage():
    with pytest.raises(LegacyError):
        LegacyPlan([
            ReleaseStage("a", ["x"], requires_ack="b"),
            ReleaseStage("b", ["y"]),
        ])


def test_releasable_immediate():
    plan = _plan()
    open_stages = plan.releasable(fired_at=0.0, now=0.0)
    assert [s.name for s in open_stages] == ["immediate"]


def test_releasable_after_delay():
    plan = _plan()
    open_stages = plan.releasable(fired_at=0.0, now=3600.0)
    assert [s.name for s in open_stages] == ["immediate", "accounts"]


def test_releasable_gated_on_ack():
    plan = _plan()
    # archive delay has passed but accounts not yet acknowledged.
    open_stages = plan.releasable(fired_at=0.0, now=90000.0)
    assert "archive" not in [s.name for s in open_stages]
    plan.acknowledge("accounts")
    open_stages = plan.releasable(fired_at=0.0, now=90000.0)
    assert "archive" in [s.name for s in open_stages]


def test_releasable_now_before_fire_raises():
    plan = _plan()
    with pytest.raises(LegacyError):
        plan.releasable(fired_at=100.0, now=50.0)


def test_acknowledge_unknown_raises():
    plan = _plan()
    with pytest.raises(LegacyError):
        plan.acknowledge("ghost")


def test_next_gate():
    plan = _plan()
    gate = plan.next_gate(fired_at=0.0, now=0.0)
    assert gate["stage"] == "accounts"
    assert gate["opens_at"] == 3600.0


def test_next_gate_none_when_all_open():
    plan = _plan()
    assert plan.next_gate(fired_at=0.0, now=10**9) is None


def test_render():
    plan = _plan()
    text = plan.render()
    assert "# Legacy release plan" in text
    assert "immediate" in text
    assert "accounts" in text
    assert "acknowledged" in text
    assert "email credentials" in text
