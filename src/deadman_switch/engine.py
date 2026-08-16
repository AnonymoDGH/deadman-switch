"""The switch engine: clock + state machine + event log + heartbeat.

This module is the heart of the expansion. It wraps the original
file-based heartbeat in an explicit engine that:

* uses an injected clock (so tests and the simulator are deterministic),
* drives the lifecycle through the SwitchStateMachine,
* records every beat, warning, trip, and fire in the hash-chained EventLog,
* supports a grace period (WARNING) between first silence and TRIPPED,
* and exposes a single tick() that advances the engine by one check.

The original module-level functions (heartbeat/check/watch) still work and
are unchanged; this engine is the richer object-oriented path used by the
new CLI commands, the simulator, and the recovery/quorum layers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional

from .clock import Clock, default_clock
from .events import EventLog
from .payloads import PayloadAction, PayloadResult, build_action
from .state import State, SwitchStateMachine
from .store import SwitchStore

__all__ = ["SwitchConfig", "Switch", "SwitchError"]


class SwitchError(RuntimeError):
    """Raised for engine misuse."""


class SwitchConfig:
    """Tunable parameters for one switch."""

    def __init__(self, ttl_seconds: float, grace_seconds: float = 0.0,
                 heartbeat_path: Optional[Path] = None) -> None:
        if ttl_seconds <= 0:
            raise SwitchError("ttl_seconds must be positive")
        if grace_seconds < 0:
            raise SwitchError("grace_seconds must be >= 0")
        self.ttl_seconds = float(ttl_seconds)
        self.grace_seconds = float(grace_seconds)
        self.heartbeat_path = heartbeat_path

    def to_dict(self) -> Dict:
        return {
            "ttl_seconds": self.ttl_seconds,
            "grace_seconds": self.grace_seconds,
            "heartbeat_path": (str(self.heartbeat_path)
                               if self.heartbeat_path else None),
        }


class Switch:
    """One dead man's switch, driven by an explicit clock.

    The engine does not touch the wall clock; every notion of "now" comes
    from the injected clock. That is what makes the whole lifecycle
    reproducible: feed a FixedClock, advance it, and watch the switch move
    through ARMED -> WARNING -> TRIPPED -> FIRED deterministically.
    """

    def __init__(self, config: SwitchConfig, clock: Optional[Clock] = None,
                 on_fire: Optional[Callable[[], None]] = None,
                 payload: Optional[Dict] = None) -> None:
        self.config = config
        self._clock = clock or default_clock()
        self._sm = SwitchStateMachine(clock=self._clock)
        self._log = EventLog()
        self._on_fire = on_fire
        self._payload_action: Optional[PayloadAction] = (
            build_action(payload) if payload is not None else None)
        self._last_result: Optional[PayloadResult] = None
        self._last_beat: Optional[float] = None
        self._warned_at: Optional[float] = None

    # -- introspection ------------------------------------------------------

    @property
    def state(self) -> str:
        return self._sm.state

    @property
    def log(self) -> EventLog:
        return self._log

    @property
    def last_beat(self) -> Optional[float]:
        return self._last_beat

    @property
    def last_result(self) -> Optional[PayloadResult]:
        """The result of the most recent payload execution, if any."""
        return self._last_result

    def age(self) -> Optional[float]:
        """Seconds since the last beat, or None if never beaten."""
        if self._last_beat is None:
            return None
        return self._clock.now() - self._last_beat

    def slack(self) -> Optional[float]:
        """Seconds of silence left before the next stage, or None."""
        age = self.age()
        if age is None:
            return None
        if self.state == State.ARMED:
            return max(0.0, self.config.ttl_seconds - age)
        if self.state == State.WARNING:
            return max(0.0, self.config.grace_seconds -
                       (self._clock.now() - (self._warned_at or 0.0)))
        return 0.0

    # -- lifecycle ----------------------------------------------------------

    def arm(self) -> None:
        """Arm the switch and stamp the first heartbeat."""
        self._sm.arm()
        self._stamp_beat()
        self._log.append("arm", self.config.to_dict(), at=self._clock.now())

    def beat(self) -> None:
        """Stamp a heartbeat, rescuing the switch if it was warning/tripped."""
        if self._sm.state in (State.WARNING, State.TRIPPED):
            self._sm.beat()
            self._log.append("rescue", {}, at=self._clock.now())
        self._stamp_beat()
        self._log.append("beat", {}, at=self._clock.now())

    def disarm(self) -> None:
        self._sm.disarm()
        self._log.append("disarm", {}, at=self._clock.now())

    def cancel(self) -> None:
        """Authenticated abort from the TRIPPED state."""
        self._sm.cancel()
        self._log.append("cancel", {}, at=self._clock.now())

    def _stamp_beat(self) -> None:
        self._last_beat = self._clock.now()
        self._warned_at = None
        if self.config.heartbeat_path is not None:
            path = Path(self.config.heartbeat_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

    # -- the tick -----------------------------------------------------------

    def tick(self) -> str:
        """Advance the engine by one check. Returns the resulting state.

        This is the single place where silence is measured and the state
        machine is advanced. Call it on a schedule (or drive it from the
        simulator). It fires the payload exactly once, on the transition to
        FIRED.
        """
        if self._sm.state == State.DISARMED:
            return self.state
        if self._sm.is_terminal:
            return self.state

        age = self.age()
        if age is None:
            # Never beaten while armed: treat as immediate silence.
            age = self.config.ttl_seconds + 1

        if self._sm.state == State.ARMED:
            if age > self.config.ttl_seconds:
                if self.config.grace_seconds > 0:
                    self._sm.warn()
                    self._warned_at = self._clock.now()
                    self._log.append("warn", {"age": age},
                                     at=self._clock.now())
                else:
                    self._trip_and_maybe_fire(age)
        elif self._sm.state == State.WARNING:
            since_warn = self._clock.now() - (self._warned_at or 0.0)
            if since_warn > self.config.grace_seconds:
                self._trip_and_maybe_fire(age)
        elif self._sm.state == State.TRIPPED:
            # Already tripped; a later tick fires the payload.
            self._fire()

        return self.state

    def _trip_and_maybe_fire(self, age: float) -> None:
        self._sm.trip()
        self._log.append("trip", {"age": age}, at=self._clock.now())
        if self.config.grace_seconds <= 0:
            self._fire()

    def _fire(self) -> None:
        if self._sm.state != State.TRIPPED:
            return
        self._sm.fire()
        self._log.append("fire", {}, at=self._clock.now())
        if self._payload_action is not None:
            self._last_result = self._payload_action.execute()
            self._log.append("payload", self._last_result.to_dict(),
                             at=self._clock.now())
        if self._on_fire is not None:
            self._on_fire()

    # -- persistence --------------------------------------------------------

    def to_state(self) -> Dict:
        """Serialize the engine's resumable state to a plain dict."""
        return {
            "state": self._sm.state,
            "config": self.config.to_dict(),
            "last_beat": self._last_beat,
            "warned_at": self._warned_at,
            "now": self._clock.now(),
        }

    def save(self, store: SwitchStore) -> None:
        """Persist the engine state and event log to a store."""
        store.save(self.to_state(), self._log)

    @classmethod
    def load(cls, store: SwitchStore, clock: Optional[Clock] = None,
             on_fire: Optional[Callable[[], None]] = None,
             payload: Optional[Dict] = None) -> "Switch":
        """Restore an engine from a store.

        The state machine is replayed from the event log so the restored
        switch lands in the same lifecycle state, and the event log chain is
        verified on the way in.
        """
        data = store.load(verify_chain=True)
        state = data["state"]
        config = SwitchConfig(
            ttl_seconds=state["config"]["ttl_seconds"],
            grace_seconds=state["config"].get("grace_seconds", 0.0),
            heartbeat_path=(Path(state["config"]["heartbeat_path"])
                            if state["config"].get("heartbeat_path") else None),
        )
        engine = cls(config, clock=clock, on_fire=on_fire, payload=payload)
        engine._log = data["log"]
        engine._last_beat = state.get("last_beat")
        engine._warned_at = state.get("warned_at")
        # Replay the lifecycle from the recorded events.
        target = state.get("state", State.DISARMED)
        engine._replay_to(target)
        return engine

    def _replay_to(self, target: str) -> None:
        """Drive the fresh state machine to the recorded state.

        Uses the direct ARMED->TRIPPED transition so the replay is
        unambiguous regardless of whether a grace period was configured.
        """
        order = {
            State.DISARMED: [],
            State.ARMED: ["arm"],
            State.WARNING: ["arm", "warn"],
            State.TRIPPED: ["arm", "trip"],
            State.FIRED: ["arm", "trip", "fire"],
        }
        for step in order.get(target, []):
            getattr(self._sm, step)()
