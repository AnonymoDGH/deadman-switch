"""Key and token rotation scheduling.

Long-lived secrets rot: a cancel token that has existed for a year has had
a year to leak. This module schedules rotation of the switch's secrets --
the heartbeat key, the cancel token, and the escrow passphrase -- so they
are refreshed on a fixed cadence and the handler always knows which
generation is current.

Each secret has a rotation period. The scheduler tracks when each was last
rotated and reports which are due now, which are overdue, and when the next
rotation is due. It is pure date arithmetic over a clock, so it is
deterministic and testable. The scheduler never touches the real secrets;
it only tracks their generations.
"""

from __future__ import annotations

from typing import Dict, List, Optional

__all__ = [
    "RotationError",
    "SecretSchedule",
    "RotationScheduler",
    "DEFAULT_PERIODS",
]


class RotationError(ValueError):
    """Raised for scheduler misuse."""


#: Default rotation periods in seconds.
DEFAULT_PERIODS = {
    "heartbeat_key": 30 * 24 * 3600,   # monthly
    "cancel_token": 90 * 24 * 3600,    # quarterly
    "escrow_passphrase": 180 * 24 * 3600,  # twice a year
}


class SecretSchedule:
    """Rotation state for one secret."""

    def __init__(self, name: str, period_seconds: float,
                 last_rotated: float) -> None:
        if not name.strip():
            raise RotationError("secret name must not be empty")
        if period_seconds <= 0:
            raise RotationError("period must be positive")
        self.name = name.strip()
        self.period_seconds = period_seconds
        self.last_rotated = last_rotated
        self.generation = 1

    def next_due(self) -> float:
        """The timestamp at which this secret is next due for rotation."""
        return self.last_rotated + self.period_seconds

    def is_due(self, now: float) -> bool:
        """True if the secret should be rotated at or before now."""
        return now >= self.next_due()

    def rotate(self, now: float) -> int:
        """Record a rotation at now; returns the new generation."""
        if now < self.last_rotated:
            raise RotationError("cannot rotate backwards in time")
        self.last_rotated = now
        self.generation += 1
        return self.generation

    def to_dict(self) -> Dict:
        return {"name": self.name,
                "period_seconds": self.period_seconds,
                "last_rotated": self.last_rotated,
                "generation": self.generation}


class RotationScheduler:
    """Tracks rotation for a set of secrets."""

    def __init__(self, now: float,
                 periods: Optional[Dict[str, float]] = None) -> None:
        self._schedules: Dict[str, SecretSchedule] = {}
        for name, period in (periods or DEFAULT_PERIODS).items():
            self._schedules[name] = SecretSchedule(name, period, now)

    def names(self) -> List[str]:
        return sorted(self._schedules)

    def get(self, name: str) -> SecretSchedule:
        if name not in self._schedules:
            raise RotationError(f"no secret named {name!r}")
        return self._schedules[name]

    def due(self, now: float) -> List[str]:
        """Names of secrets due for rotation at or before now."""
        return sorted(name for name, schedule in self._schedules.items()
                      if schedule.is_due(now))

    def overdue(self, now: float, grace_seconds: float = 0.0) -> List[str]:
        """Names of secrets past their due date by more than grace."""
        return sorted(
            name for name, schedule in self._schedules.items()
            if now > schedule.next_due() + grace_seconds)

    def rotate(self, name: str, now: float) -> int:
        """Rotate one secret; returns its new generation."""
        return self.get(name).rotate(now)

    def rotate_all_due(self, now: float) -> List[str]:
        """Rotate every secret that is due; returns the names rotated."""
        rotated = []
        for name in self.due(now):
            self._schedules[name].rotate(now)
            rotated.append(name)
        return rotated

    def next_due(self) -> Optional[Dict]:
        """The soonest upcoming rotation, or None if no secrets."""
        if not self._schedules:
            return None
        name = min(self._schedules,
                   key=lambda n: self._schedules[n].next_due())
        schedule = self._schedules[name]
        return {"name": name, "due_at": schedule.next_due(),
                "generation": schedule.generation}

    def to_dict(self) -> Dict:
        return {name: schedule.to_dict()
                for name, schedule in self._schedules.items()}
