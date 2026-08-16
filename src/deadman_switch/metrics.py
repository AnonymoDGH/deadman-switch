"""Heartbeat regularity metrics.

Whether a switch fired is only one question; HOW the operator was beating is
the other. A healthy operator beats on a steady rhythm. Irregular beats --
long gaps followed by bursts, or steadily widening intervals -- can indicate
trouble before the TTL is ever crossed. This module analyzes a series of
beat timestamps and reports on the rhythm.

It computes the intervals between beats, their mean and jitter (standard
deviation), the largest gap, and a punctuality score against an expected
cadence. The output is a plain dict so it can be logged, charted, or fed to
the report module. Everything is pure arithmetic on a list of timestamps, so
it is trivially deterministic and testable.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

__all__ = [
    "MetricsError",
    "intervals",
    "basic_stats",
    "largest_gap",
    "punctuality",
    "heartbeat_report",
]


class MetricsError(ValueError):
    """Raised for invalid metric inputs."""


def intervals(beats: Sequence[float]) -> List[float]:
    """The time between consecutive beats.

    Beats are sorted first, so out-of-order input is handled. Requires at
    least two beats.
    """
    if len(beats) < 2:
        raise MetricsError("need at least 2 beats for intervals")
    ordered = sorted(beats)
    return [b - a for a, b in zip(ordered, ordered[1:])]


def basic_stats(beats: Sequence[float]) -> Dict[str, float]:
    """Mean interval, jitter (std dev), min, and max.

    Returns a dict with count, mean, jitter, min, and max. Jitter is the
    population standard deviation of the intervals.
    """
    gaps = intervals(beats)
    n = len(gaps)
    mean = sum(gaps) / n
    variance = sum((g - mean) ** 2 for g in gaps) / n
    return {
        "count": float(len(beats)),
        "mean": mean,
        "jitter": math.sqrt(variance),
        "min": min(gaps),
        "max": max(gaps),
    }


def largest_gap(beats: Sequence[float]) -> Dict[str, float]:
    """The single longest silence between two consecutive beats."""
    gaps = intervals(beats)
    ordered = sorted(beats)
    idx = max(range(len(gaps)), key=lambda i: gaps[i])
    return {
        "duration": gaps[idx],
        "from": ordered[idx],
        "to": ordered[idx + 1],
    }


def punctuality(beats: Sequence[float], expected_interval: float,
                tolerance: float = 0.25) -> Dict[str, float]:
    """Score how closely the beats follow an expected cadence.

    A beat interval within tolerance (a fraction) of the expected interval
    counts as on-time. Returns the on-time fraction and the counts.
    """
    if expected_interval <= 0:
        raise MetricsError("expected_interval must be positive")
    if not 0 <= tolerance <= 1:
        raise MetricsError("tolerance must be in [0, 1]")
    gaps = intervals(beats)
    lo = expected_interval * (1 - tolerance)
    hi = expected_interval * (1 + tolerance)
    on_time = sum(1 for g in gaps if lo <= g <= hi)
    return {
        "on_time": float(on_time),
        "total": float(len(gaps)),
        "score": on_time / len(gaps) if gaps else 1.0,
    }


def heartbeat_report(beats: Sequence[float],
                     expected_interval: Optional[float] = None) -> Dict:
    """A full rhythm report for a series of beats.

    If expected_interval is given, punctuality is included. Requires at
    least two beats.
    """
    if len(beats) < 2:
        raise MetricsError("need at least 2 beats for a report")
    report: Dict = {
        "stats": basic_stats(beats),
        "largest_gap": largest_gap(beats),
    }
    if expected_interval is not None:
        report["punctuality"] = punctuality(beats, expected_interval)
    return report
