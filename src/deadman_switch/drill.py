"""Rehearsal and readiness scoring.

A switch is only trustworthy if the operator has actually practiced using it.
The first time someone arms a switch should not be the first time they beat,
answer a proof-of-life challenge, or execute a cancel. This module runs
rehearsal drills and scores them, producing a readiness meter like the one a
handler would want before trusting a switch in the field.

A drill is a sequence of named steps, each with an expected duration. The
operator performs each step and records how long it took and whether it
succeeded. The scorer turns that into a 0-100 readiness meter, weighting
speed and accuracy, and flags any step that failed outright. A drill is
"passing" when the meter clears the threshold and no critical step failed.
"""

from __future__ import annotations

from typing import Dict, List, Optional

__all__ = [
    "DrillError",
    "DrillStep",
    "DrillResult",
    "Drill",
    "DEFAULT_DRILL_STEPS",
    "PASS_THRESHOLD",
]

#: Readiness meter must reach this to pass.
PASS_THRESHOLD = 80


class DrillError(ValueError):
    """Raised for drill misuse."""


class DrillStep:
    """One step in a rehearsal drill."""

    def __init__(self, name: str, expected_seconds: float,
                 critical: bool = False) -> None:
        if not name.strip():
            raise DrillError("step name must not be empty")
        if expected_seconds <= 0:
            raise DrillError("expected_seconds must be positive")
        self.name = name.strip()
        self.expected_seconds = expected_seconds
        self.critical = critical


class DrillResult:
    """The recorded outcome of one step."""

    def __init__(self, step: DrillStep, elapsed: float, ok: bool) -> None:
        if elapsed < 0:
            raise DrillError("elapsed must be >= 0")
        self.step = step
        self.elapsed = elapsed
        self.ok = ok

    @property
    def speed_ratio(self) -> float:
        """elapsed / expected; <= 1.0 means at or under the target time."""
        return self.elapsed / self.step.expected_seconds


class Drill:
    """Runs a rehearsal and scores readiness."""

    def __init__(self, steps: Optional[List[DrillStep]] = None) -> None:
        self._steps = list(steps) if steps is not None else [
            DrillStep(*s) for s in DEFAULT_DRILL_STEPS]
        self._results: List[DrillResult] = []

    @property
    def steps(self) -> List[DrillStep]:
        return list(self._steps)

    def record(self, step_name: str, elapsed: float, ok: bool) -> DrillResult:
        """Record the outcome of one step by name."""
        step = None
        for candidate in self._steps:
            if candidate.name == step_name:
                step = candidate
                break
        if step is None:
            raise DrillError(f"unknown step {step_name!r}")
        result = DrillResult(step, elapsed, ok)
        self._results.append(result)
        return result

    @property
    def results(self) -> List[DrillResult]:
        return list(self._results)

    def complete(self) -> bool:
        """True once every step has been recorded at least once."""
        done = {r.step.name for r in self._results}
        return all(s.name in done for s in self._steps)

    def failed_critical(self) -> List[str]:
        """Names of critical steps that were recorded as failures."""
        return [r.step.name for r in self._results
                if r.step.critical and not r.ok]

    def meter(self) -> float:
        """Score readiness 0-100.

        Each step contributes equally. A step scores on accuracy (ok) and
        speed (how close to the expected time). A failed step scores 0. A
        step done in under the expected time scores full speed credit; slower
        steps are scaled down.
        """
        if not self._results:
            return 0.0
        total = 0.0
        for result in self._results:
            if not result.ok:
                continue
            ratio = result.speed_ratio
            speed_credit = 1.0 if ratio <= 1.0 else max(0.0, 1.0 - (ratio - 1.0))
            total += (0.5 + 0.5 * speed_credit)
        return 100.0 * total / len(self._results)

    def passed(self, threshold: float = PASS_THRESHOLD) -> bool:
        """True if the meter clears the threshold and no critical step failed."""
        return (self.complete()
                and self.meter() >= threshold
                and not self.failed_critical())

    def summary(self) -> Dict:
        return {
            "steps": len(self._steps),
            "recorded": len(self._results),
            "complete": self.complete(),
            "meter": round(self.meter(), 1),
            "failed_critical": self.failed_critical(),
            "passed": self.passed(),
        }


#: The default rehearsal: arm, beat, answer a challenge, cancel.
DEFAULT_DRILL_STEPS = [
    ("arm", 30.0, True),
    ("beat", 10.0, True),
    ("proof-of-life", 60.0, True),
    ("cancel", 30.0, True),
    ("verify-log", 45.0, False),
]
