"""Tamper-evident event log for the dead man's switch.

A dead man's switch is only trustworthy if you can prove what it did and
when. This module records every lifecycle event into a hash-chained log:
each entry carries the hash of the previous entry, so deleting, reordering,
or editing any record breaks every hash after it.

The chain is append-only and can be serialized to disk and re-verified. It
is deliberately simple -- a SHA-256 chain over canonical JSON -- which is
enough to detect tampering and to give a handler confidence in the timeline.
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional

__all__ = [
    "GENESIS_HASH",
    "EventLogError",
    "Event",
    "EventLog",
]

#: The hash that seeds the first entry in every chain.
GENESIS_HASH = "0" * 64


class EventLogError(RuntimeError):
    """Raised when the event log is corrupted or misused."""


class Event:
    """One recorded event in the chain."""

    def __init__(self, seq: int, kind: str, detail: Dict, at: float,
                 prev_hash: str, hash: str) -> None:
        self.seq = seq
        self.kind = kind
        self.detail = detail
        self.at = at
        self.prev_hash = prev_hash
        self.hash = hash

    def to_dict(self) -> Dict:
        return {
            "seq": self.seq,
            "kind": self.kind,
            "detail": self.detail,
            "at": self.at,
            "prev_hash": self.prev_hash,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Event":
        return cls(seq=data["seq"], kind=data["kind"], detail=data["detail"],
                   at=data["at"], prev_hash=data["prev_hash"],
                   hash=data["hash"])


def _canonical(seq: int, kind: str, detail: Dict, at: float,
               prev_hash: str) -> str:
    """The canonical string that gets hashed for one entry."""
    payload = {
        "seq": seq,
        "kind": kind,
        "detail": detail,
        "at": at,
        "prev_hash": prev_hash,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _hash_entry(seq: int, kind: str, detail: Dict, at: float,
                prev_hash: str) -> str:
    return hashlib.sha256(_canonical(seq, kind, detail, at,
                                     prev_hash).encode("utf-8")).hexdigest()


class EventLog:
    """An append-only, hash-chained event log."""

    def __init__(self) -> None:
        self._events: List[Event] = []

    def __len__(self) -> int:
        return len(self._events)

    @property
    def events(self) -> List[Event]:
        return list(self._events)

    @property
    def head_hash(self) -> str:
        """The hash of the most recent entry, or GENESIS_HASH if empty."""
        return self._events[-1].hash if self._events else GENESIS_HASH

    def append(self, kind: str, detail: Optional[Dict] = None,
               at: float = 0.0) -> Event:
        """Append one event and return it."""
        detail = detail or {}
        seq = len(self._events)
        prev_hash = self.head_hash
        entry_hash = _hash_entry(seq, kind, detail, at, prev_hash)
        event = Event(seq=seq, kind=kind, detail=detail, at=at,
                      prev_hash=prev_hash, hash=entry_hash)
        self._events.append(event)
        return event

    def verify(self) -> bool:
        """Recompute every hash and confirm the chain is intact."""
        prev_hash = GENESIS_HASH
        for event in self._events:
            if event.prev_hash != prev_hash:
                return False
            expected = _hash_entry(event.seq, event.kind, event.detail,
                                   event.at, event.prev_hash)
            if event.hash != expected:
                return False
            prev_hash = event.hash
        return True

    def first_broken(self) -> Optional[int]:
        """The seq of the first broken link, or None if the chain is clean."""
        prev_hash = GENESIS_HASH
        for event in self._events:
            if event.prev_hash != prev_hash:
                return event.seq
            expected = _hash_entry(event.seq, event.kind, event.detail,
                                   event.at, event.prev_hash)
            if event.hash != expected:
                return event.seq
            prev_hash = event.hash
        return None

    def kinds(self) -> Dict[str, int]:
        """Count events by kind."""
        counts: Dict[str, int] = {}
        for event in self._events:
            counts[event.kind] = counts.get(event.kind, 0) + 1
        return counts

    def to_text(self) -> str:
        """Serialize the log to a JSON-lines string."""
        return "\n".join(json.dumps(e.to_dict(), sort_keys=True)
                          for e in self._events)

    @classmethod
    def from_text(cls, text: str) -> "EventLog":
        """Parse to_text() output back into a log."""
        log = cls()
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EventLogError(f"corrupt event line: {exc}") from exc
            log._events.append(Event.from_dict(data))
        return log
