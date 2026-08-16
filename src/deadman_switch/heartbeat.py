"""Rich, signed heartbeat records.

The original heartbeat is just a file touch -- no content, no integrity. An
attacker who can touch the file can keep the switch alive. This module
upgrades the heartbeat into a signed record that carries metadata and can be
verified.

A HeartbeatRecord binds together:

* a monotonic sequence number (replay protection),
* the timestamp of the beat,
* an optional operator note,
* an HMAC over all of it under the shared key.

The switch (or a store) can verify a record's signature and freshness before
accepting it as a genuine beat. Records serialize to JSON so they can be
written to the heartbeat file, sent over a channel, or logged. This turns
"someone touched the file" into "the right someone, holding the key, beat at
this time with this sequence number."
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from typing import Dict, Optional

__all__ = [
    "HeartbeatError",
    "HeartbeatRecord",
    "sign_heartbeat_record",
    "verify_heartbeat_record",
    "HeartbeatLedger",
]


class HeartbeatError(ValueError):
    """Raised for heartbeat misuse."""


@dataclass
class HeartbeatRecord:
    """One signed heartbeat."""

    seq: int
    ts: float
    note: str = ""
    mac: str = ""

    def __post_init__(self) -> None:
        if self.seq < 0:
            raise HeartbeatError("seq must be >= 0")

    def to_dict(self) -> Dict:
        return {"seq": self.seq, "ts": self.ts, "note": self.note,
                "mac": self.mac}

    @classmethod
    def from_dict(cls, data: Dict) -> "HeartbeatRecord":
        try:
            return cls(seq=data["seq"], ts=data["ts"],
                       note=data.get("note", ""), mac=data.get("mac", ""))
        except KeyError as exc:
            raise HeartbeatError(f"heartbeat missing field {exc}") from exc

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "HeartbeatRecord":
        try:
            return cls.from_dict(json.loads(text))
        except json.JSONDecodeError as exc:
            raise HeartbeatError(f"corrupt heartbeat json: {exc}") from exc


def _mac_payload(seq: int, ts: float, note: str) -> str:
    payload = {"seq": seq, "ts": ts, "note": note, "kind": "heartbeat"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sign_heartbeat_record(key: bytes, seq: int, ts: float,
                          note: str = "") -> HeartbeatRecord:
    """Produce a signed heartbeat record."""
    mac = hmac.new(key, _mac_payload(seq, ts, note).encode("utf-8"),
                   "sha256").hexdigest()
    return HeartbeatRecord(seq=seq, ts=ts, note=note, mac=mac)


def verify_heartbeat_record(key: bytes, record: HeartbeatRecord) -> bool:
    """Check a record's MAC (not its freshness)."""
    expected = hmac.new(key,
                        _mac_payload(record.seq, record.ts,
                                     record.note).encode("utf-8"),
                        "sha256").hexdigest()
    return hmac.compare_digest(expected, record.mac)


class HeartbeatLedger:
    """Accepts signed heartbeats and enforces replay protection.

    The ledger remembers the highest sequence number it has accepted and
    rejects anything at or below it, as well as anything with a bad MAC. It
    keeps the accepted records so a handler can inspect the rhythm and notes.
    """

    def __init__(self, key: bytes) -> None:
        self._key = key
        self._last_seq = -1
        self._records: list = []
        self._rejected = 0

    @property
    def last_seq(self) -> int:
        return self._last_seq

    @property
    def records(self) -> list:
        return list(self._records)

    @property
    def rejected(self) -> int:
        return self._rejected

    def accept(self, record: HeartbeatRecord) -> bool:
        """Accept or reject one heartbeat. Returns True if accepted."""
        if not verify_heartbeat_record(self._key, record):
            self._rejected += 1
            return False
        if record.seq <= self._last_seq:
            self._rejected += 1
            return False
        self._last_seq = record.seq
        self._records.append(record)
        return True

    def beat_times(self) -> list:
        """The timestamps of all accepted beats, in order."""
        return [r.ts for r in self._records]

    def latest_note(self) -> Optional[str]:
        """The note on the most recent accepted beat, if any."""
        if not self._records:
            return None
        return self._records[-1].note or None
