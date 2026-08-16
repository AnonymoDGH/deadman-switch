"""Mission-control orchestrator for one switch.

The individual modules each do one thing: the engine tracks state, the
store persists, the dispatcher notifies contacts, the journal records
context, the beacon proves liveness outward. A handler should not have to
wire those together by hand every time. This module provides the Handler,
which owns one switch end to end and exposes the operations a handler
actually performs:

* arm / beat / disarm / cancel
* tick (advance time and react: warn, trip, fire, notify)
* journal entries attached to beats
* automatic dispatch to contacts on warn/trip/fire
* persistence after every state change

The Handler is deterministic when given a FixedClock, so the whole mission
can be replayed in tests.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .clock import Clock, FixedClock
from .contacts import Roster
from .dispatcher import Dispatcher
from .engine import Switch, SwitchConfig
from .journal import Journal
from .state import State
from .store import SwitchStore

__all__ = ["HandlerError", "Handler"]


class HandlerError(RuntimeError):
    """Raised for handler misuse."""


class Handler:
    """Owns one switch end to end."""

    def __init__(self, switch_id: str, config: SwitchConfig,
                 clock: Optional[Clock] = None,
                 store: Optional[SwitchStore] = None,
                 roster: Optional[Roster] = None,
                 dispatcher: Optional[Dispatcher] = None,
                 payload: Optional[Dict] = None,
                 on_fire: Optional[Callable[[], None]] = None) -> None:
        if not switch_id.strip():
            raise HandlerError("switch_id must not be empty")
        self.switch_id = switch_id.strip()
        self._clock = clock or FixedClock()
        self._store = store
        self._journal = Journal()
        self._roster = roster or Roster()
        self._dispatcher = dispatcher or Dispatcher(self._roster)
        self._switch = Switch(config, clock=self._clock, on_fire=on_fire,
                              payload=payload)
        self._config = config
        self._dispatched: List[str] = []

    # -- accessors ---------------------------------------------------------

    @property
    def state(self) -> str:
        return self._switch.state

    @property
    def journal(self) -> Journal:
        return self._journal

    @property
    def switch(self) -> Switch:
        return self._switch

    @property
    def dispatched_levels(self) -> List[str]:
        """Escalation levels already dispatched (no duplicates)."""
        return list(self._dispatched)

    # -- operations --------------------------------------------------------

    def arm(self, note: str = "") -> None:
        """Arm the switch and optionally journal the reason."""
        self._switch.arm()
        if note:
            self._journal.add(self._clock.now(), note, ["arm"])
        self._persist()

    def beat(self, note: str = "") -> None:
        """Stamp a heartbeat, optionally with a journal note."""
        self._switch.beat()
        if note:
            self._journal.add(self._clock.now(), note, ["beat"])
        self._persist()

    def disarm(self) -> None:
        self._switch.disarm()
        self._persist()

    def cancel(self) -> None:
        self._switch.cancel()
        self._journal.add(self._clock.now(), "cancelled by handler",
                          ["cancel"])
        self._persist()

    def tick(self) -> str:
        """Advance the switch one tick and react to any state change.

        On entering WARNING/TRIPPED/FIRED the handler dispatches the
        matching alert level to the roster exactly once per level.
        """
        before = self._switch.state
        after = self._switch.tick()
        if after != before:
            self._react(after)
        self._persist()
        return after

    def _react(self, new_state: str) -> None:
        level_map = {
            State.WARNING: "warn",
            State.TRIPPED: "trip",
            State.FIRED: "fire",
        }
        level = level_map.get(new_state)
        if level is None or level in self._dispatched:
            return
        self._dispatcher.dispatch(level, self.switch_id)
        self._dispatched.append(level)
        self._journal.add(self._clock.now(),
                          f"switch entered {new_state}; notified {level}",
                          ["escalation", level])

    def _persist(self) -> None:
        if self._store is not None:
            self._switch.save(self._store)

    # -- reporting ---------------------------------------------------------

    def summary(self) -> Dict:
        """A snapshot of everything the handler knows."""
        return {
            "switch_id": self.switch_id,
            "state": self.state,
            "beats": len([e for e in self._switch.log.events
                          if e.kind == "beat"]),
            "journal_entries": len(self._journal),
            "dispatched": self.dispatched_levels,
            "contacts": len(self._roster),
        }
