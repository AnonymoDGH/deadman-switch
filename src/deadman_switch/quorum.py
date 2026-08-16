"""Quorum approval for cancelling a tripped switch.

A single cancel token is powerful: whoever holds it can abort the switch.
For high-stakes payloads you may want to require that several trusted
parties agree before a cancel is honored. This module implements that as a
quorum: each party casts a signed approval, and the cancel only proceeds
once a configured threshold of distinct, valid approvals is collected.

Approvals are bound to a specific switch and a specific "round" (so stale
approvals from a previous trip cannot be replayed), and each party may
approve only once per round. The quorum object is pure and deterministic,
so it can be driven by the engine, the CLI, and the tests alike.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

__all__ = [
    "QuorumError",
    "Approval",
    "Quorum",
]


class QuorumError(ValueError):
    """Raised for quorum misuse."""


class Approval:
    """One party's signed approval to cancel."""

    def __init__(self, party: str, switch_id: str, round: int,
                 valid: bool = True) -> None:
        if not party.strip():
            raise QuorumError("party must not be empty")
        if not switch_id.strip():
            raise QuorumError("switch_id must not be empty")
        if round < 0:
            raise QuorumError("round must be >= 0")
        self.party = party.strip()
        self.switch_id = switch_id.strip()
        self.round = round
        self.valid = valid

    def __repr__(self) -> str:
        return (f"Approval({self.party!r}, {self.switch_id!r}, "
                f"round={self.round}, valid={self.valid})")


class Quorum:
    """Collects approvals and decides when the cancel threshold is met."""

    def __init__(self, switch_id: str, threshold: int,
                 parties: List[str]) -> None:
        if not switch_id.strip():
            raise QuorumError("switch_id must not be empty")
        if threshold < 1:
            raise QuorumError("threshold must be >= 1")
        if threshold > len(parties):
            raise QuorumError("threshold cannot exceed the number of parties")
        if len(set(parties)) != len(parties):
            raise QuorumError("parties must be distinct")
        self.switch_id = switch_id.strip()
        self.threshold = threshold
        self._parties = list(parties)
        self._round = 0
        self._approved: Set[str] = set()
        self._rejected: List[Approval] = []

    @property
    def round(self) -> int:
        return self._round

    @property
    def parties(self) -> List[str]:
        return list(self._parties)

    @property
    def approved_parties(self) -> Set[str]:
        return set(self._approved)

    def begin_round(self) -> int:
        """Start a fresh approval round, clearing prior approvals."""
        self._round += 1
        self._approved.clear()
        return self._round

    def cast(self, approval: Approval) -> bool:
        """Record one approval. Returns True if the quorum is now met.

        An approval is rejected (and recorded) if it is for the wrong
        switch, the wrong round, an unknown party, already cast, or marked
        invalid. Rejections never count toward the threshold.
        """
        if approval.switch_id != self.switch_id:
            self._rejected.append(approval)
            return False
        if approval.round != self._round:
            self._rejected.append(approval)
            return False
        if approval.party not in self._parties:
            self._rejected.append(approval)
            return False
        if not approval.valid:
            self._rejected.append(approval)
            return False
        if approval.party in self._approved:
            self._rejected.append(approval)
            return False
        self._approved.add(approval.party)
        return self.is_met()

    def is_met(self) -> bool:
        """True once enough distinct valid approvals are collected."""
        return len(self._approved) >= self.threshold

    def remaining(self) -> int:
        """How many more approvals are needed."""
        return max(0, self.threshold - len(self._approved))

    @property
    def rejected(self) -> List[Approval]:
        return list(self._rejected)

    def status(self) -> Dict:
        """A snapshot of the quorum state."""
        return {
            "switch_id": self.switch_id,
            "round": self._round,
            "threshold": self.threshold,
            "approved": sorted(self._approved),
            "remaining": self.remaining(),
            "met": self.is_met(),
            "rejected_count": len(self._rejected),
        }
