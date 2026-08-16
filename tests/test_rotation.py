"""Tests for deadman_switch.rotation -- key/token rotation scheduling."""

from __future__ import annotations

import pytest

from deadman_switch.rotation import (
    DEFAULT_PERIODS, RotationError, RotationScheduler, SecretSchedule,
)


def test_schedule_validation():
    with pytest.raises(RotationError):
        SecretSchedule("  ", 100, 0.0)
    with pytest.raises(RotationError):
        SecretSchedule("x", 0, 0.0)


def test_schedule_due():
    schedule = SecretSchedule("key", period_seconds=100, last_rotated=0.0)
    assert schedule.is_due(50) is False
    assert schedule.is_due(100) is True
    assert schedule.next_due() == 100


def test_schedule_rotate():
    schedule = SecretSchedule("key", period_seconds=100, last_rotated=0.0)
    gen = schedule.rotate(100.0)
    assert gen == 2
    assert schedule.last_rotated == 100.0
    assert schedule.next_due() == 200.0


def test_schedule_rotate_backwards_raises():
    schedule = SecretSchedule("key", period_seconds=100, last_rotated=50.0)
    with pytest.raises(RotationError):
        schedule.rotate(10.0)


def test_scheduler_default_secrets():
    scheduler = RotationScheduler(now=0.0)
    assert scheduler.names() == sorted(DEFAULT_PERIODS)


def test_scheduler_get_unknown():
    scheduler = RotationScheduler(now=0.0)
    with pytest.raises(RotationError):
        scheduler.get("bogus")


def test_scheduler_due_and_overdue():
    periods = {"a": 100.0, "b": 200.0}
    scheduler = RotationScheduler(now=0.0, periods=periods)
    assert scheduler.due(50) == []
    assert scheduler.due(100) == ["a"]
    assert scheduler.due(200) == ["a", "b"]
    assert scheduler.overdue(150) == ["a"]
    assert scheduler.overdue(150, grace_seconds=60) == []


def test_scheduler_rotate():
    scheduler = RotationScheduler(now=0.0, periods={"a": 100.0})
    gen = scheduler.rotate("a", 100.0)
    assert gen == 2
    assert scheduler.due(150) == []


def test_scheduler_rotate_all_due():
    periods = {"a": 100.0, "b": 200.0}
    scheduler = RotationScheduler(now=0.0, periods=periods)
    rotated = scheduler.rotate_all_due(250.0)
    assert rotated == ["a", "b"]
    assert scheduler.due(250.0) == []


def test_scheduler_next_due():
    periods = {"a": 100.0, "b": 50.0}
    scheduler = RotationScheduler(now=0.0, periods=periods)
    nxt = scheduler.next_due()
    assert nxt["name"] == "b"
    assert nxt["due_at"] == 50.0


def test_scheduler_to_dict():
    scheduler = RotationScheduler(now=0.0, periods={"a": 100.0})
    data = scheduler.to_dict()
    assert data["a"]["generation"] == 1
    assert data["a"]["period_seconds"] == 100.0
