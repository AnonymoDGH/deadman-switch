"""Explicit lifecycle state machine for the dead man's switch.

The original switch has two implicit states -- armed or tripped -- and the
transition is buried inside check(). That makes it hard to add a grace
period, a warning stage, or a cancel path without tangling the logic.

This module models the lifecycle as an explicit finite state machine:

    DISARMED --arm--> ARMED --silence--> WARNING --silence--> TRIPPED --fire--> FIRED
       ^                 |                   |
       |                 +---beat------------+---beat---> ARMED
       +------------------disarm/cancel-------------------+

Each transition is validated, timestamped by an injected clock, and recorded
so the event log can reconstruct exactly how a switch reached its current
state. Invalid transitions raise StateError instead of silently doing the
wrong thing.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .clock import Clock, default_clock

__all__ = [
    "State",
    "StateError",
    "Transition",
    "SwitchStateMachine",
]


class State:
    """The lifecycle states of a switch."""

    DISARMED = "disarmed"
    ARMED = "armed"
    WARNING = "warning"
    TRIPPED = "tripped"
    FIRED = "fired"

    #: Which states are "live" (the operator is still presumed safe).
    LIVE = (ARMED, WARNING)
    #: Terminal states.
    TERMINAL = (FIRED,)


class StateError(RuntimeError):
    """Raised on an invalid state transition."""


class Transition:
    """One recorded state change."""

    def __init__(self, from_state: str, to_state: str, reason: str,
                 at: float) -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        self.at = at

    def __repr__(self) -> str:
        return (f"Transition({self.from_state} -> {self.to_state} "
                f"@ {self.at:.0f}, {self.reason!r})")


#: Allowed transitions: from_state -> {to_state: set of reasons}.
_ALLOWED: Dict[str, Dict[str, set]] = {
    State.DISARMED: {State.ARMED: {"arm"}},
    State.ARMED: {
        State.WARNING: {"silence"},
        State.TRIPPED: {"silence"},   # no grace period: straight to tripped
        State.DISARMED: {"disarm"},
    },
    State.WARNING: {
        State.ARMED: {"beat"},
        State.TRIPPED: {"silence"},
        State.DISARMED: {"disarm"},
    },
    State.TRIPPED: {
        State.ARMED: {"beat"},       # rescued before the payload fires
        State.FIRED: {"fire"},
        State.DISARMED: {"cancel"},  # authenticated abort
    },
    State.FIRED: {},                  # terminal
}


class SwitchStateMachine:
    """The switch lifecycle as an explicit, auditable state machine."""

    def __init__(self, clock: Optional[Clock] = None) -> None:
        self._clock = clock or default_clock()
        self._state = State.DISARMED
        self._history: List[Transition] = []

    @property
    def state(self) -> str:
        return self._state

    @property
    def history(self) -> List[Transition]:
        return list(self._history)

    @property
    def is_live(self) -> bool:
        return self._state in State.LIVE

    @property
    def is_terminal(self) -> bool:
        return self._state in State.TERMINAL

    def _move(self, to_state: str, reason: str) -> Transition:
        allowed = _ALLOWED.get(self._state, {})
        if to_state not in allowed or reason not in allowed[to_state]:
            raise StateError(
                f"cannot {reason!r} from {self._state!r} to {to_state!r}")
        transition = Transition(self._state, to_state, reason,
                                self._clock.now())
        self._state = to_state
        self._history.append(transition)
        return transition

    def arm(self) -> Transition:
        return self._move(State.ARMED, "arm")

    def warn(self) -> Transition:
        """Enter the grace period after the first stretch of silence."""
        return self._move(State.WARNING, "silence")

    def trip(self) -> Transition:
        """Silence outlasted the grace period; the switch is tripped."""
        return self._move(State.TRIPPED, "silence")

    def beat(self) -> Transition:
        """A heartbeat rescues the switch back to ARMED."""
        return self._move(State.ARMED, "beat")

    def fire(self) -> Transition:
        """The payload executed."""
        return self._move(State.FIRED, "fire")

    def disarm(self) -> Transition:
        return self._move(State.DISARMED, "disarm")

    def cancel(self) -> Transition:
        """Authenticated abort from the TRIPPED state."""
        return self._move(State.DISARMED, "cancel")

    def can(self, to_state: str, reason: str) -> bool:
        """Whether a transition is currently legal."""
        return (to_state in _ALLOWED.get(self._state, {})
                and reason in _ALLOWED[self._state][to_state])
