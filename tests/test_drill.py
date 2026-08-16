"""Tests for deadman_switch.drill -- rehearsal and readiness scoring."""

from __future__ import annotations

import pytest

from deadman_switch.drill import (
    Drill, DrillError, DrillResult, DrillStep, PASS_THRESHOLD,
)


def _fast_drill():
    drill = Drill()
    for step in drill.steps:
        drill.record(step.name, elapsed=step.expected_seconds * 0.5, ok=True)
    return drill


def test_step_validation():
    with pytest.raises(DrillError):
        DrillStep("  ", 10)
    with pytest.raises(DrillError):
        DrillStep("x", 0)


def test_result_validation():
    with pytest.raises(DrillError):
        DrillResult(DrillStep("x", 10), elapsed=-1, ok=True)


def test_default_steps():
    drill = Drill()
    names = [s.name for s in drill.steps]
    assert "arm" in names
    assert "proof-of-life" in names


def test_record_unknown_step():
    drill = Drill()
    with pytest.raises(DrillError):
        drill.record("nonexistent", 1.0, True)


def test_complete():
    drill = Drill()
    assert drill.complete() is False
    _ = _fast_drill()
    assert _.complete() is True


def test_meter_perfect():
    drill = _fast_drill()
    assert drill.meter() == 100.0


def test_meter_slow_steps():
    drill = Drill()
    for step in drill.steps:
        drill.record(step.name, elapsed=step.expected_seconds * 1.5, ok=True)
    assert drill.meter() < 100.0
    assert drill.meter() > 0.0


def test_meter_failed_step_zero():
    drill = Drill()
    drill.record("arm", 10, ok=False)
    assert drill.meter() == 0.0


def test_meter_empty():
    assert Drill().meter() == 0.0


def test_failed_critical():
    drill = Drill()
    drill.record("arm", 10, ok=False)
    assert drill.failed_critical() == ["arm"]


def test_passed_requires_complete():
    drill = Drill()
    drill.record("arm", 10, ok=True)
    assert drill.passed() is False  # not complete


def test_passed_full():
    assert _fast_drill().passed() is True


def test_passed_critical_failure():
    drill = _fast_drill()
    drill.record("arm", 10, ok=False)  # re-record arm as failed
    assert drill.passed() is False


def test_summary_shape():
    drill = _fast_drill()
    summary = drill.summary()
    assert summary["complete"] is True
    assert summary["meter"] == 100.0
    assert summary["passed"] is True
    assert summary["failed_critical"] == []


def test_speed_ratio():
    step = DrillStep("x", 10)
    result = DrillResult(step, elapsed=5, ok=True)
    assert result.speed_ratio == 0.5
