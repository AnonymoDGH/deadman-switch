"""Deterministic scenario simulator for the dead man's switch.

Before trusting a switch configuration with a real payload, you want to
know how it behaves under realistic patterns of life: regular heartbeats,
a long flight with no signal, a missed beat here and there, or total
silence. This module simulates those scenarios against the engine using a
FixedClock, so the whole timeline runs in microseconds and is fully
reproducible.

A scenario is a list of (time_offset, action) events. Actions are "beat"
or nothing (silence). The simulator advances the clock, applies beats,
ticks the engine, and records the state after each step. The result is a
timeline you can assert on: did the switch fire? when? did a late beat
rescue it?
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .clock import FixedClock
from .engine import Switch, SwitchConfig
from .state import State

__all__ = [
    "SimError",
    "Scenario",
    "SimResult",
    "run_scenario",
    "regular_beats",
    "silence_after",
    "missed_beat",
]


class SimError(ValueError):
    """Raised for malformed scenarios."""


class Scenario:
    """A scripted timeline of beats over a total duration."""

    def __init__(self, total_seconds: float,
                 beats: List[float]) -> None:
        if total_seconds <= 0:
            raise SimError("total_seconds must be positive")
        if any(b < 0 or b > total_seconds for b in beats):
            raise SimError("beat times must lie within [0, total_seconds]")
        self.total_seconds = float(total_seconds)
        self.beats = sorted(beats)


class SimResult:
    """The outcome of one simulated run."""

    def __init__(self, final_state: str, fired: bool,
                 fired_at: Optional[float],
                 timeline: List[Dict]) -> None:
        self.final_state = final_state
        self.fired = fired
        self.fired_at = fired_at
        self.timeline = timeline

    def state_at(self, t: float) -> Optional[str]:
        """The engine state at or just before time t."""
        result = None
        for step in self.timeline:
            if step["t"] <= t:
                result = step["state"]
            else:
                break
        return result


def run_scenario(config: SwitchConfig, scenario: Scenario,
                 tick_interval: float = 1.0) -> SimResult:
    """Run one scenario against a fresh engine and return the timeline.

    The clock starts at 0. Beats are applied at their scheduled offsets;
    the engine is ticked every tick_interval seconds. The payload is a
    no-op notify so nothing real fires.
    """
    if tick_interval <= 0:
        raise SimError("tick_interval must be positive")
    clock = FixedClock(start=0.0)
    engine = Switch(config, clock=clock,
                    payload={"type": "notify", "label": "sim"})
    engine.arm()

    timeline: List[Dict] = []
    fired_at: Optional[float] = None
    beat_index = 0
    t = 0.0

    timeline.append({"t": 0.0, "state": engine.state, "event": "arm"})

    while t < scenario.total_seconds:
        # Apply any beats scheduled at or before the next tick.
        next_t = min(t + tick_interval, scenario.total_seconds)
        while (beat_index < len(scenario.beats)
               and scenario.beats[beat_index] <= next_t):
            clock.set(scenario.beats[beat_index])
            engine.beat()
            timeline.append({"t": scenario.beats[beat_index],
                             "state": engine.state, "event": "beat"})
            beat_index += 1
        clock.set(next_t)
        state = engine.tick()
        timeline.append({"t": next_t, "state": state, "event": "tick"})
        if state == State.FIRED and fired_at is None:
            fired_at = next_t
        t = next_t

    return SimResult(final_state=engine.state,
                     fired=fired_at is not None,
                     fired_at=fired_at,
                     timeline=timeline)


# ---------------------------------------------------------------------------
# Scenario builders
# ---------------------------------------------------------------------------

def regular_beats(total_seconds: float, interval: float) -> Scenario:
    """A healthy operator beating on a fixed interval."""
    if interval <= 0:
        raise SimError("interval must be positive")
    beats = []
    t = interval
    while t <= total_seconds:
        beats.append(t)
        t += interval
    return Scenario(total_seconds, beats)


def silence_after(total_seconds: float, interval: float,
                  silence_from: float) -> Scenario:
    """Regular beats until silence_from, then nothing (the operator is gone)."""
    beats = []
    t = interval
    while t <= total_seconds and t < silence_from:
        beats.append(t)
        t += interval
    return Scenario(total_seconds, beats)


def missed_beat(total_seconds: float, interval: float,
                missed_index: int) -> Scenario:
    """Regular beats with exactly one beat missing (a flaky day)."""
    beats = []
    t = interval
    index = 0
    while t <= total_seconds:
        if index != missed_index:
            beats.append(t)
        index += 1
        t += interval
    return Scenario(total_seconds, beats)
