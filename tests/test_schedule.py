"""Tests for deadman_switch.schedule -- beat schedule planning."""

from __future__ import annotations

import pytest

from deadman_switch.schedule import (
    BeatPlan, ScheduleError, cron_hint, plan_beats, validate_manual_schedule,
)


def test_plan_beats_spacing():
    plan = plan_beats(ttl_seconds=60, window_seconds=180, safety=0.5)
    assert plan.interval == 30
    assert plan.beats == [0, 30, 60, 90, 120, 150, 180]


def test_plan_beats_margin():
    plan = plan_beats(ttl_seconds=60, window_seconds=100, safety=0.5)
    assert plan.margin == 30


def test_plan_beats_custom_start():
    plan = plan_beats(ttl_seconds=60, window_seconds=60, safety=0.5, start=10)
    assert plan.beats[0] == 10


def test_plan_beats_validation():
    with pytest.raises(ScheduleError):
        plan_beats(ttl_seconds=0, window_seconds=100)
    with pytest.raises(ScheduleError):
        plan_beats(ttl_seconds=60, window_seconds=0)
    with pytest.raises(ScheduleError):
        plan_beats(ttl_seconds=60, window_seconds=100, safety=1.5)


def test_due_before_and_next_after():
    plan = plan_beats(ttl_seconds=60, window_seconds=120, safety=0.5)
    assert plan.due_before(45) == [0, 30]
    assert plan.next_after(45) == 60
    assert plan.next_after(999) is None


def test_validate_manual_schedule_safe():
    assert validate_manual_schedule([0, 30, 60, 90], ttl_seconds=60) == []


def test_validate_manual_schedule_gap():
    problems = validate_manual_schedule([0, 30, 120], ttl_seconds=60)
    assert any("exceeds TTL" in p for p in problems)


def test_validate_manual_schedule_empty():
    problems = validate_manual_schedule([], ttl_seconds=60)
    assert any("no beats" in p for p in problems)


def test_validate_manual_schedule_bad_ttl():
    problems = validate_manual_schedule([0, 30], ttl_seconds=0)
    assert any("positive" in p for p in problems)


def test_cron_hint_buckets():
    assert "every minute" in cron_hint(30)
    assert "every 5 minutes" in cron_hint(4 * 60)
    assert "every 15 minutes" in cron_hint(10 * 60)
    assert "hourly" in cron_hint(45 * 60)
    assert "daily" in cron_hint(24 * 3600)


def test_cron_hint_invalid():
    with pytest.raises(ScheduleError):
        cron_hint(0)


def test_beat_plan_len():
    plan = plan_beats(ttl_seconds=60, window_seconds=60, safety=0.5)
    assert len(plan) == len(plan.beats)
