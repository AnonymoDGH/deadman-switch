"""Signed liveness beacons.

The classic switch is one-directional: it watches YOU and fires when you go
silent. But a handler may also want the reverse -- a periodic, signed
"still alive" signal they can verify without touching the switch. This
module produces and verifies those beacons.

A beacon is a small signed record: the switch id, a monotonic sequence
number, a timestamp, and an HMAC over all of it. A watcher who shares the
key can verify each beacon is authentic and fresh, and can detect both
forgery (bad MAC) and replay (reused or out-of-order sequence numbers).

Beacons are deliberately tiny and serializable so they can ride any channel
-- a file drop, a webhook body, a line in a log. The watcher keeps only the
last sequence number it accepted, which is all it needs to stay replay-safe.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Dict, Optional

__all__ = [
    "BeaconError",
    "Beacon",
    "BeaconWatcher",
    "sign_beacon",
    "verify_beacon",
]


class BeaconError(ValueError):
    """Raised for beacon misuse."""


class Beacon:
    """One signed liveness beacon."""

    def __init__(self, switch_id: str, seq: int, ts: float, mac: str) -> None:
        if not switch_id.strip():
            raise BeaconError("switch_id must not be empty")
        if seq < 0:
            raise BeaconError("seq must be >= 0")
        self.switch_id = switch_id.strip()
        self.seq = seq
        self.ts = ts
        self.mac = mac

    def to_dict(self) -> Dict:
        return {"switch_id": self.switch_id, "seq": self.seq,
                "ts": self.ts, "mac": self.mac}

    @classmethod
    def from_dict(cls, data: Dict) -> "Beacon":
        try:
            return cls(switch_id=data["switch_id"], seq=data["seq"],
                       ts=data["ts"], mac=data["mac"])
        except KeyError as exc:
            raise BeaconError(f"beacon missing field {exc}") from exc

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "Beacon":
        try:
            return cls.from_dict(json.loads(text))
        except json.JSONDecodeError as exc:
            raise BeaconError(f"corrupt beacon json: {exc}") from exc


def _mac_payload(switch_id: str, seq: int, ts: float) -> str:
    payload = {"switch_id": switch_id, "seq": seq, "ts": ts,
               "kind": "beacon"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sign_beacon(key: bytes, switch_id: str, seq: int, ts: float) -> Beacon:
    """Produce a signed beacon."""
    mac = hmac.new(key, _mac_payload(switch_id, seq, ts).encode("utf-8"),
                   "sha256").hexdigest()
    return Beacon(switch_id=switch_id, seq=seq, ts=ts, mac=mac)


def verify_beacon(key: bytes, beacon: Beacon) -> bool:
    """Check a beacon's MAC (not its freshness)."""
    expected = hmac.new(key,
                        _mac_payload(beacon.switch_id, beacon.seq,
                                     beacon.ts).encode("utf-8"),
                        "sha256").hexdigest()
    return hmac.compare_digest(expected, beacon.mac)


class BeaconWatcher:
    """The receiving side: accepts authentic, fresh beacons.

    The watcher remembers the highest sequence number it has accepted and
    rejects anything at or below it (replay) as well as anything with a bad
    MAC (forgery). It counts accepted and rejected beacons so a handler can
    see the health of the channel.
    """

    def __init__(self, key: bytes, switch_id: str) -> None:
        self._key = key
        self._switch_id = switch_id.strip()
        self._last_seq = -1
        self._last_ts: Optional[float] = None
        self._accepted = 0
        self._rejected = 0

    @property
    def last_seq(self) -> int:
        return self._last_seq

    @property
    def last_ts(self) -> Optional[float]:
        """Timestamp of the most recently accepted beacon."""
        return self._last_ts

    @property
    def accepted(self) -> int:
        return self._accepted

    @property
    def rejected(self) -> int:
        return self._rejected

    def receive(self, beacon: Beacon) -> bool:
        """Accept or reject one beacon. Returns True if accepted."""
        if beacon.switch_id != self._switch_id:
            self._rejected += 1
            return False
        if not verify_beacon(self._key, beacon):
            self._rejected += 1
            return False
        if beacon.seq <= self._last_seq:
            self._rejected += 1
            return False
        self._last_seq = beacon.seq
        self._last_ts = beacon.ts
        self._accepted += 1
        return True

    def is_overdue(self, now: float, max_age: float) -> bool:
        """True if no beacon has been accepted within max_age seconds.

        A watcher that has stopped receiving fresh beacons treats the
        operator as potentially gone -- the mirror image of the switch's own
        silence detection.
        """
        if self._last_ts is None:
            return True  # never heard anything
        return (now - self._last_ts) > max_age
