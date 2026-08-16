"""Duress codes for covert signaling.

A duress code is a secret that looks like a normal response but covertly
signals "I am being coerced." If an adversary forces the operator to beat
the switch or answer a check-in, the operator uses the duress variant
instead of the genuine one. To the adversary it looks compliant; to the
handler it silently raises the alarm.

This module generates paired codes from a seed -- a genuine code and a
duress code that are easy for the operator to tell apart but look equally
plausible to an observer -- and verifies which one was presented. Codes are
short word sequences drawn from a fixed, unambiguous wordlist so they can
be spoken over a phone without spelling errors.

The module is deterministic for a given seed, so the operator and handler
can independently derive the same pair without transmitting it.
"""

from __future__ import annotations

import hashlib
import random
from typing import Dict, List, Tuple

__all__ = [
    "DuressError",
    "WORDLIST",
    "generate_codes",
    "classify",
]


class DuressError(ValueError):
    """Raised for duress code misuse."""


#: A small, phonetically distinct wordlist for spoken codes.
WORDLIST = [
    "alpha", "bravo", "cedar", "delta", "ember", "frost", "grain", "haven",
    "ivory", "jumbo", "kayak", "lemon", "mango", "noble", "otter", "piano",
    "quilt", "rover", "sable", "tiger", "unity", "vivid", "whale", "xenon",
    "yacht", "zebra",
]


def _derive_ints(seed: str, count: int, salt: str) -> List[int]:
    """Derive `count` pseudo-random indices from a seed via SHA-256."""
    out: List[int] = []
    counter = 0
    while len(out) < count:
        digest = hashlib.sha256(
            f"{seed}:{salt}:{counter}".encode("utf-8")).digest()
        for i in range(0, len(digest) - 3, 4):
            if len(out) >= count:
                break
            out.append(int.from_bytes(digest[i:i + 4], "big"))
        counter += 1
    return out


def generate_codes(seed: str, words: int = 3) -> Dict[str, str]:
    """Generate a genuine/duress code pair from a seed.

    Both codes are `words` words long, drawn from WORDLIST. The duress code
    is derived from a different salt so it never collides with the genuine
    code. Deterministic for a given seed.

    Returns:
        {"genuine": "...", "duress": "..."}
    """
    if not seed.strip():
        raise DuressError("seed must not be empty")
    if words < 2:
        raise DuressError("codes need at least 2 words")

    def build(salt: str) -> str:
        indices = _derive_ints(seed, words, salt)
        return " ".join(WORDLIST[i % len(WORDLIST)] for i in indices)

    genuine = build("genuine")
    duress = build("duress")
    if genuine == duress:  # astronomically unlikely, but never ship equal codes
        duress = build("duress-2")
    return {"genuine": genuine, "duress": duress}


def classify(presented: str, seed: str, words: int = 3) -> str:
    """Classify a presented code against the pair derived from seed.

    Returns:
        "genuine"  -- the operator is free and compliant.
        "duress"   -- the operator is coerced; raise the alarm quietly.
        "invalid"  -- not either code; treat as a failed check-in.
    """
    codes = generate_codes(seed, words)
    normalized = " ".join(presented.strip().lower().split())
    if normalized == codes["genuine"]:
        return "genuine"
    if normalized == codes["duress"]:
        return "duress"
    return "invalid"
