"""Proof-of-life challenges for the dead man's switch.

A heartbeat proves a file was touched. It does not prove the operator is
alive, conscious, and acting of their own free will. An attacker who
captures the operator can keep touching the heartbeat file forever.

This module adds a challenge layer. Periodically the switch issues a
challenge that only the real, un-coerced operator can answer:

* a cognitive task (arithmetic, recall) that a coerced or impaired person
  is likely to fail or delay,
* a duress bit: the operator answers, but can flip a hidden flag that says
  "I am answering under duress." A duress answer LOOKS like a normal beat
  to the attacker but secretly trips the switch into a covert alarm state.

Challenges are deterministic under a seed so tests and the simulator can
reproduce them. The duress mechanism is the point: it turns the heartbeat
from "someone touched the file" into "the right someone, freely, answered."
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

__all__ = [
    "ProofError",
    "Challenge",
    "ChallengeResult",
    "ProofOfLife",
    "make_arithmetic_challenge",
    "make_recall_challenge",
]


class ProofError(ValueError):
    """Raised for proof-of-life misuse."""


@dataclass(frozen=True)
class Challenge:
    """One proof-of-life challenge."""

    kind: str            # "arithmetic" | "recall"
    prompt: str
    answer: str
    window_seconds: float  # how long the operator has to answer

    def __post_init__(self) -> None:
        if self.window_seconds <= 0:
            raise ProofError("window_seconds must be positive")


@dataclass
class ChallengeResult:
    """The outcome of answering a challenge."""

    correct: bool
    duress: bool
    elapsed: float
    challenge: Challenge


def make_arithmetic_challenge(rng: random.Random,
                              window_seconds: float = 300.0) -> Challenge:
    """A small arithmetic task: hard to automate, easy for a clear mind."""
    a = rng.randrange(13, 89)
    b = rng.randrange(7, 49)
    op = rng.choice(["+", "-", "*"])
    if op == "+":
        answer = a + b
    elif op == "-":
        answer = a - b
    else:
        answer = a * b
    return Challenge(
        kind="arithmetic",
        prompt=f"What is {a} {op} {b}?",
        answer=str(answer),
        window_seconds=window_seconds,
    )


_RECALL_FACTS: List[Dict[str, str]] = [
    {"q": "What is the safe word you set at arming?", "a": "SAFEWORD"},
    {"q": "What city is your dead-drop backup in?", "a": "BACKUPCITY"},
    {"q": "What is your handler's call sign?", "a": "CALLSIGN"},
]


def make_recall_challenge(rng: random.Random,
                          facts: Optional[List[Dict[str, str]]] = None,
                          window_seconds: float = 300.0) -> Challenge:
    """A recall task on a pre-agreed secret only the operator knows."""
    pool = facts or _RECALL_FACTS
    fact = rng.choice(pool)
    return Challenge(
        kind="recall",
        prompt=fact["q"],
        answer=fact["a"],
        window_seconds=window_seconds,
    )


class ProofOfLife:
    """Issues and grades proof-of-life challenges for one switch.

    The operator answers each challenge with a response string plus an
    optional duress flag. A correct, non-duress answer counts as a genuine
    heartbeat. A duress answer is recorded as a covert alarm: to anyone
    watching it looks like a normal beat, but the switch knows to escalate
    silently.
    """

    def __init__(self, seed: Optional[int] = None,
                 facts: Optional[List[Dict[str, str]]] = None) -> None:
        self._rng = random.Random(seed)
        self._facts = facts
        self._pending: Optional[Challenge] = None
        self._history: List[ChallengeResult] = []
        self._duress_count = 0

    def issue(self, kind: str = "arithmetic",
              window_seconds: float = 300.0) -> Challenge:
        """Issue a new challenge, replacing any pending one."""
        if kind == "arithmetic":
            self._pending = make_arithmetic_challenge(self._rng, window_seconds)
        elif kind == "recall":
            self._pending = make_recall_challenge(self._rng, self._facts,
                                                  window_seconds)
        else:
            raise ProofError(f"unknown challenge kind {kind!r}")
        return self._pending

    @property
    def pending(self) -> Optional[Challenge]:
        return self._pending

    def answer(self, response: str, duress: bool = False,
               elapsed: float = 0.0) -> ChallengeResult:
        """Grade the operator's answer to the pending challenge.

        Raises:
            ProofError: If no challenge is pending.
        """
        if self._pending is None:
            raise ProofError("no challenge pending; call issue() first")
        correct = response.strip().lower() == self._pending.answer.strip().lower()
        result = ChallengeResult(correct=correct, duress=duress,
                                 elapsed=elapsed, challenge=self._pending)
        self._history.append(result)
        if duress:
            self._duress_count += 1
        self._pending = None
        return result

    @property
    def history(self) -> List[ChallengeResult]:
        return list(self._history)

    @property
    def duress_count(self) -> int:
        return self._duress_count

    def is_coerced(self) -> bool:
        """True if any answer carried the duress flag."""
        return self._duress_count > 0

    def pass_rate(self) -> float:
        """Fraction of answered challenges that were correct."""
        if not self._history:
            return 1.0
        correct = sum(1 for r in self._history if r.correct)
        return round(correct / len(self._history), 3)
