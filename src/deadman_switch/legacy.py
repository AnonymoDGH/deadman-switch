"""Digital legacy release planner.

The most sensitive use of a dead man's switch is releasing a digital legacy
when the operator does not come back: account credentials for family,
final messages, instructions for closing down services. Doing that all at
once is risky and overwhelming. This module plans the release in stages,
each gated on its own condition, so the legacy unfolds in a controlled
order.

A LegacyPlan is an ordered list of ReleaseStages. Each stage has a name,
the items it releases, and a gate: either a delay after the fire, or a
requirement that an earlier stage was acknowledged by a beneficiary. The
planner computes which stages are releasable at a given time and renders
the plan for the executor. Everything is deterministic data and time
arithmetic.
"""

from __future__ import annotations

from typing import Dict, List, Optional

__all__ = [
    "LegacyError",
    "ReleaseStage",
    "LegacyPlan",
]


class LegacyError(ValueError):
    """Raised for legacy plan misuse."""


class ReleaseStage:
    """One stage of a legacy release."""

    def __init__(self, name: str, items: List[str],
                 delay_seconds: float = 0.0,
                 requires_ack: Optional[str] = None) -> None:
        if not name.strip():
            raise LegacyError("stage name must not be empty")
        if not items:
            raise LegacyError("stage must release at least one item")
        if delay_seconds < 0:
            raise LegacyError("delay must be >= 0")
        self.name = name.strip()
        self.items = list(items)
        self.delay_seconds = delay_seconds
        self.requires_ack = requires_ack

    def to_dict(self) -> Dict:
        return {"name": self.name, "items": self.items,
                "delay_seconds": self.delay_seconds,
                "requires_ack": self.requires_ack}


class LegacyPlan:
    """An ordered, gated legacy release plan."""

    def __init__(self, stages: List[ReleaseStage]) -> None:
        if not stages:
            raise LegacyError("plan must have at least one stage")
        names = [stage.name for stage in stages]
        if len(names) != len(set(names)):
            raise LegacyError("stage names must be distinct")
        for stage in stages:
            if stage.requires_ack is not None:
                if stage.requires_ack not in names:
                    raise LegacyError(
                        f"stage {stage.name!r} requires unknown stage "
                        f"{stage.requires_ack!r}")
                if names.index(stage.requires_ack) >= names.index(stage.name):
                    raise LegacyError(
                        f"stage {stage.name!r} cannot require a later stage")
        self._stages = list(stages)
        self._acked: set = set()

    @property
    def stages(self) -> List[ReleaseStage]:
        return list(self._stages)

    def acknowledge(self, stage_name: str) -> None:
        """Record that a beneficiary acknowledged a released stage."""
        if not any(stage.name == stage_name for stage in self._stages):
            raise LegacyError(f"unknown stage {stage_name!r}")
        self._acked.add(stage_name)

    def is_acked(self, stage_name: str) -> bool:
        return stage_name in self._acked

    def releasable(self, fired_at: float, now: float) -> List[ReleaseStage]:
        """Stages whose gate is open at time now.

        A stage is releasable once (fired_at + delay) has passed and, if it
        requires an acknowledgement, that earlier stage has been
        acknowledged.
        """
        if now < fired_at:
            raise LegacyError("now cannot precede the fire time")
        open_stages: List[ReleaseStage] = []
        for stage in self._stages:
            if now < fired_at + stage.delay_seconds:
                continue
            if stage.requires_ack is not None:
                if stage.requires_ack not in self._acked:
                    continue
            open_stages.append(stage)
        return open_stages

    def next_gate(self, fired_at: float, now: float) -> Optional[Dict]:
        """The soonest future gate, for telling the executor what to wait for."""
        future = []
        for stage in self._stages:
            opens_at = fired_at + stage.delay_seconds
            if opens_at > now:
                future.append({"stage": stage.name, "opens_at": opens_at})
        if not future:
            return None
        return min(future, key=lambda entry: entry["opens_at"])

    def render(self) -> str:
        """Render the plan for the executor."""
        lines = ["# Legacy release plan", ""]
        for index, stage in enumerate(self._stages, start=1):
            delay = stage.delay_seconds
            gate = f"after +{delay:.0f}s" if delay else "immediately"
            if stage.requires_ack:
                gate += f", once '{stage.requires_ack}' is acknowledged"
            lines.append(f"{index}. **{stage.name}** — {gate}")
            for item in stage.items:
                lines.append(f"   - {item}")
            lines.append("")
        return "\n".join(lines)
