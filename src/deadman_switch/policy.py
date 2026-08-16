"""Escalation policy for the dead man's switch.

A single payload is a blunt instrument. In practice you want a ladder:
after the first stretch of silence, send a gentle reminder; after a longer
silence, notify a trusted contact; only after a final, unambiguous silence
do you release the real payload. This module models that ladder as an
ordered list of stages, each with its own threshold and payload.

The policy is pure data plus evaluation logic: given an age of silence it
returns the highest stage that has been reached. The engine (or a handler)
decides what to do with that. Stages are validated at construction so a
misconfigured ladder is caught before the switch is armed, not while it is
firing.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .payloads import build_action

__all__ = [
    "PolicyError",
    "Stage",
    "EscalationPolicy",
    "default_policy",
]


class PolicyError(ValueError):
    """Raised for a misconfigured escalation policy."""


class Stage:
    """One rung of the escalation ladder."""

    def __init__(self, name: str, after_seconds: float,
                 payload: Dict) -> None:
        if not name.strip():
            raise PolicyError("stage name must not be empty")
        if after_seconds < 0:
            raise PolicyError("after_seconds must be >= 0")
        self.name = name.strip()
        self.after_seconds = float(after_seconds)
        self.payload = dict(payload)
        # Validate the payload now, not at fire time.
        build_action(self.payload)

    def __repr__(self) -> str:
        return f"Stage({self.name!r}, after {self.after_seconds:.0f}s)"


class EscalationPolicy:
    """An ordered escalation ladder.

    Stages must have strictly increasing thresholds; evaluating an age of
    silence returns every stage whose threshold has been crossed, in order,
    so the caller can fire each one exactly once.
    """

    def __init__(self, stages: List[Stage]) -> None:
        if not stages:
            raise PolicyError("a policy needs at least one stage")
        thresholds = [s.after_seconds for s in stages]
        if thresholds != sorted(thresholds):
            raise PolicyError("stages must be ordered by after_seconds")
        if len(set(thresholds)) != len(thresholds):
            raise PolicyError("stage thresholds must be distinct")
        self._stages = list(stages)

    @property
    def stages(self) -> List[Stage]:
        return list(self._stages)

    def __len__(self) -> int:
        return len(self._stages)

    def reached(self, age_seconds: float) -> List[Stage]:
        """Every stage whose threshold the silence has crossed."""
        return [s for s in self._stages if age_seconds >= s.after_seconds]

    def current(self, age_seconds: float) -> Optional[Stage]:
        """The highest stage reached, or None if silence is below stage one."""
        reached = self.reached(age_seconds)
        return reached[-1] if reached else None

    def final_threshold(self) -> float:
        """The silence length at which the last stage triggers."""
        return self._stages[-1].after_seconds

    def to_dict(self) -> Dict:
        return {
            "stages": [
                {"name": s.name, "after_seconds": s.after_seconds,
                 "payload": s.payload}
                for s in self._stages
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "EscalationPolicy":
        stages = [Stage(s["name"], s["after_seconds"], s["payload"])
                  for s in data.get("stages", [])]
        return cls(stages)


def default_policy(ttl_seconds: float) -> EscalationPolicy:
    """A sensible three-stage ladder anchored to a base TTL.

    * remind  -- at 1x TTL, a gentle self-reminder
    * alert   -- at 2x TTL, notify a trusted contact
    * release -- at 3x TTL, the real payload
    """
    if ttl_seconds <= 0:
        raise PolicyError("ttl_seconds must be positive")
    return EscalationPolicy([
        Stage("remind", ttl_seconds,
              {"type": "print", "message": "Reminder: heartbeat overdue."}),
        Stage("alert", ttl_seconds * 2,
              {"type": "notify", "label": "trusted-contact"}),
        Stage("release", ttl_seconds * 3,
              {"type": "print", "message": "The dead man's switch has fired."}),
    ])
