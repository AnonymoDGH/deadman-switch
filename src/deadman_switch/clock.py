"""Deterministic clocks for the dead man's switch.

The original switch reads time.time() directly, which makes tests slow and
flaky -- you have to actually sleep for the TTL to elapse. This module
introduces a tiny clock abstraction so the higher-level state machine can
be driven by a controllable clock in tests while still using the wall clock
in production.

Two clocks are provided:

* WallClock -- the real thing. now() returns time.time().
* FixedClock -- a hand-cranked clock for tests. You advance it explicitly
  with advance(), so a "24 hour silence" scenario runs in microseconds.

Everything downstream takes a clock as an optional argument and defaults to
a shared WallClock, so production behavior is unchanged.
"""

from __future__ import annotations

import time
from typing import Optional

__all__ = ["Clock", "WallClock", "FixedClock", "default_clock"]


class Clock:
    """The clock interface. Subclasses provide now()."""

    def now(self) -> float:
        """Current time as a Unix timestamp (seconds)."""
        raise NotImplementedError

    def sleep(self, seconds: float) -> None:
        """Advance the clock by sleeping. FixedClock fast-forwards instead."""
        time.sleep(seconds)


class WallClock(Clock):
    """The real wall clock."""

    def now(self) -> float:
        return time.time()


class FixedClock(Clock):
    """A deterministic, hand-cranked clock for tests and simulation.

    Starts at a given timestamp (default 1_000_000.0) and only moves when
    advance() is called. sleep() is a fast-forward, so loops that poll and
    sleep terminate instantly in tests.
    """

    def __init__(self, start: float = 1_000_000.0) -> None:
        self._now = float(start)

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> float:
        """Move the clock forward and return the new time."""
        if seconds < 0:
            raise ValueError("cannot advance a clock backwards")
        self._now += float(seconds)
        return self._now

    def set(self, when: float) -> None:
        """Jump the clock to an absolute time."""
        self._now = float(when)

    def sleep(self, seconds: float) -> None:
        """Fast-forward instead of really sleeping."""
        self.advance(seconds)


#: The process-wide default clock. Production code uses this.
_DEFAULT: Clock = WallClock()


def default_clock() -> Clock:
    """Return the process-wide default clock."""
    return _DEFAULT
