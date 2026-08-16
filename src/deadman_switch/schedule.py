"""Beat schedule planning.

Knowing the TTL is only half the discipline; the operator also needs a
concrete plan for WHEN to beat. Beat too rarely and you live on the edge of
the TTL; beat too often and the switch becomes noise. This module plans a
beat schedule that keeps a safe margin under the TTL and tells the operator
exactly when each beat is due.

The planner spaces beats at a fixed fraction of the TTL (the safety factor),
aligns them to a readable cadence, and can render the plan as a list of
due-times or as a cron-style hint. It also validates that a proposed manual
schedule actually stays inside the TTL, so a handler can check a human-written
plan before trusting it.
"""

from __future__ import annotations

from typing import Dict, List, Optional

__all__ = [
    "ScheduleError",
    "BeatPlan",
    "plan_beats",
    "validate_manual_schedule",
    "cron_hint",
]

#: Default safety factor: beat at half the TTL so one missed beat is survivable.
DEFAULT_SAFETY = 0.5


class ScheduleError(ValueError):
    """Raised for invalid schedule parameters."""


class BeatPlan:
    """A planned sequence of beat times over a window."""

    def __init__(self, interval: float, beats: List[float],
                 ttl_seconds: float) -> None:
        self.interval = interval
        self.beats = list(beats)
        self.ttl_seconds = ttl_seconds

    def __len__(self) -> int:
        return len(self.beats)

    @property
    def margin(self) -> float:
        """Seconds of slack between beats (TTL minus interval)."""
        return self.ttl_seconds - self.interval

    def due_before(self, t: float) -> List[float]:
        """All beats due at or before time t."""
        return [b for b in self.beats if b <= t]

    def next_after(self, t: float) -> Optional[float]:
        """The first beat strictly after time t, if any."""
        for b in self.beats:
            if b > t:
                return b
        return None


def plan_beats(ttl_seconds: float, window_seconds: float,
               safety: float = DEFAULT_SAFETY,
               start: float = 0.0) -> BeatPlan:
    """Plan beats over a window, spaced at safety*TTL.

    Args:
        ttl_seconds: The switch TTL.
        window_seconds: How far ahead to plan.
        safety: Fraction of the TTL between beats (0<safety<1). Lower is
            safer (more frequent beats); 0.5 means one missed beat is fine.
        start: Time of the first beat.

    Returns:
        A BeatPlan with beats at start, start+interval, ... within the window.
    """
    if ttl_seconds <= 0:
        raise ScheduleError("ttl_seconds must be positive")
    if window_seconds <= 0:
        raise ScheduleError("window_seconds must be positive")
    if not 0 < safety < 1:
        raise ScheduleError("safety must be in (0, 1)")

    interval = ttl_seconds * safety
    beats: List[float] = []
    t = start
    while t <= start + window_seconds:
        beats.append(t)
        t += interval
    return BeatPlan(interval=interval, beats=beats, ttl_seconds=ttl_seconds)


def validate_manual_schedule(beat_times: List[float],
                             ttl_seconds: float) -> List[str]:
    """Check a human-written beat schedule stays inside the TTL.

    Returns a list of problem strings; empty means the schedule is safe.
    A gap between consecutive beats that exceeds the TTL is fatal, because
    the switch would fire in that gap.
    """
    problems: List[str] = []
    if ttl_seconds <= 0:
        problems.append("ttl_seconds must be positive")
        return problems
    if not beat_times:
        problems.append("schedule has no beats")
        return problems
    times = sorted(beat_times)
    for prev, nxt in zip(times, times[1:]):
        gap = nxt - prev
        if gap > ttl_seconds:
            problems.append(
                f"gap of {gap:.0f}s between beats exceeds TTL {ttl_seconds:.0f}s")
    return problems


def cron_hint(interval_seconds: float) -> str:
    """Suggest a cron-style cadence for a beat interval.

    Maps the interval to the nearest common cron rhythm so the operator can
    wire the heartbeat into a scheduler. This is advisory text, not a real
    crontab.
    """
    if interval_seconds <= 0:
        raise ScheduleError("interval must be positive")
    minutes = interval_seconds / 60.0
    if minutes <= 1:
        return "* * * * *   (every minute)"
    if minutes <= 5:
        return "*/5 * * * * (every 5 minutes)"
    if minutes <= 15:
        return "*/15 * * * * (every 15 minutes)"
    if minutes <= 60:
        return "0 * * * *   (hourly)"
    hours = minutes / 60.0
    if hours <= 6:
        return f"0 */{max(1, round(hours))} * * * (every {round(hours)}h)"
    return "0 0 * * *   (daily)"
