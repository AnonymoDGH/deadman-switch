"""Multi-switch watchdog manager.

A handler may run several switches at once -- one per operator, or one per
context for the same operator. Managing them individually does not scale.
This module provides a watchdog that supervises a collection of switches,
ticks them all on a shared clock, and reports the aggregate state.

The watchdog owns the clock, so every switch it manages shares one notion of
time. That makes the whole fleet deterministic: advance the clock once and
every switch advances together. It also collects which switches fired on a
given tick, so the handler can react to exactly the ones that tripped.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .clock import Clock, FixedClock, default_clock
from .engine import Switch, SwitchConfig
from .state import State

__all__ = ["WatchdogError", "Watchdog"]


class WatchdogError(RuntimeError):
    """Raised for watchdog misuse."""


class Watchdog:
    """Supervises a fleet of switches on a shared clock."""

    def __init__(self, clock: Optional[Clock] = None) -> None:
        self._clock = clock or FixedClock()
        self._switches: Dict[str, Switch] = {}

    @property
    def clock(self) -> Clock:
        return self._clock

    def add(self, name: str, config: SwitchConfig,
            payload: Optional[Dict] = None,
            on_fire: Optional[Callable[[], None]] = None) -> Switch:
        """Register a new switch under a unique name."""
        if not name.strip():
            raise WatchdogError("switch name must not be empty")
        if name in self._switches:
            raise WatchdogError(f"switch {name!r} already exists")
        switch = Switch(config, clock=self._clock, on_fire=on_fire,
                        payload=payload)
        self._switches[name] = switch
        return switch

    def get(self, name: str) -> Switch:
        if name not in self._switches:
            raise WatchdogError(f"no switch named {name!r}")
        return self._switches[name]

    def remove(self, name: str) -> None:
        self.get(name)
        del self._switches[name]

    def names(self) -> List[str]:
        return sorted(self._switches)

    def __len__(self) -> int:
        return len(self._switches)

    def arm_all(self) -> None:
        """Arm every registered switch and stamp their first beats."""
        for switch in self._switches.values():
            if switch.state == State.DISARMED:
                switch.arm()

    def beat(self, name: str) -> None:
        """Stamp a heartbeat on one named switch."""
        self.get(name).beat()

    def beat_all(self) -> None:
        """Stamp a heartbeat on every switch that can still be rescued."""
        for switch in self._switches.values():
            if switch.state in (State.ARMED, State.WARNING, State.TRIPPED):
                switch.beat()

    def tick_all(self) -> Dict[str, str]:
        """Advance every switch by one tick. Returns {name: state}.

        Also returns which switches newly fired on this tick via fired().
        """
        states: Dict[str, str] = {}
        self._fired_this_tick: List[str] = []
        for name, switch in self._switches.items():
            before = switch.state
            after = switch.tick()
            states[name] = after
            if before != State.FIRED and after == State.FIRED:
                self._fired_this_tick.append(name)
        return states

    def fired(self) -> List[str]:
        """Switches that fired on the most recent tick_all()."""
        return list(getattr(self, "_fired_this_tick", []))

    def states(self) -> Dict[str, str]:
        """The current state of every switch."""
        return {name: switch.state for name, switch in self._switches.items()}

    def live(self) -> List[str]:
        """Names of switches still in a live state."""
        return sorted(name for name, switch in self._switches.items()
                      if switch.state in (State.ARMED, State.WARNING))

    def summary(self) -> Dict[str, int]:
        """Count switches per state."""
        counts: Dict[str, int] = {}
        for switch in self._switches.values():
            counts[switch.state] = counts.get(switch.state, 0) + 1
        return counts
