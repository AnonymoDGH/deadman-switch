"""Tests for deadman_switch.policy -- escalation ladder."""

from __future__ import annotations

import pytest

from deadman_switch.policy import (
    EscalationPolicy, PolicyError, Stage, default_policy,
)


def _ladder():
    return EscalationPolicy([
        Stage("remind", 60, {"type": "print", "message": "r"}),
        Stage("alert", 120, {"type": "notify", "label": "c"}),
        Stage("release", 180, {"type": "print", "message": "f"}),
    ])


def test_stage_validation():
    with pytest.raises(PolicyError):
        Stage("  ", 60, {"type": "print"})
    with pytest.raises(PolicyError):
        Stage("x", -1, {"type": "print"})


def test_stage_validates_payload_early():
    with pytest.raises(Exception):
        Stage("x", 60, {"type": "teleport"})


def test_policy_requires_stages():
    with pytest.raises(PolicyError):
        EscalationPolicy([])


def test_policy_requires_order():
    with pytest.raises(PolicyError):
        EscalationPolicy([
            Stage("b", 120, {"type": "print"}),
            Stage("a", 60, {"type": "print"}),
        ])


def test_policy_requires_distinct_thresholds():
    with pytest.raises(PolicyError):
        EscalationPolicy([
            Stage("a", 60, {"type": "print"}),
            Stage("b", 60, {"type": "print"}),
        ])


def test_reached_below_first():
    p = _ladder()
    assert p.reached(30) == []
    assert p.current(30) is None


def test_reached_progressive():
    p = _ladder()
    assert [s.name for s in p.reached(60)] == ["remind"]
    assert [s.name for s in p.reached(150)] == ["remind", "alert"]
    assert [s.name for s in p.reached(999)] == ["remind", "alert", "release"]


def test_current_is_highest():
    p = _ladder()
    assert p.current(150).name == "alert"
    assert p.current(999).name == "release"


def test_final_threshold():
    p = _ladder()
    assert p.final_threshold() == 180


def test_roundtrip_dict():
    p = _ladder()
    restored = EscalationPolicy.from_dict(p.to_dict())
    assert len(restored) == 3
    assert [s.name for s in restored.stages] == ["remind", "alert", "release"]


def test_default_policy_anchored_to_ttl():
    p = default_policy(60)
    assert len(p) == 3
    assert p.final_threshold() == 180
    assert [s.name for s in p.stages] == ["remind", "alert", "release"]


def test_default_policy_rejects_bad_ttl():
    with pytest.raises(PolicyError):
        default_policy(0)
