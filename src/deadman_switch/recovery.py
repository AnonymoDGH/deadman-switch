"""Key recovery via Shamir secret sharing.

The disarm key is a single point of failure: lose it and you can never
cancel a tripped switch; leave it in one place and it can be stolen. This
module splits the disarm key into n shares with a threshold k, so that any
k shares can reconstruct the key but k-1 shares reveal nothing.

This is the classic "give a share to each of three trusted friends; any two
of them together can disarm" pattern. The implementation is Shamir's scheme
over GF(257) (a prime field), operating byte-by-byte on the key. It is real,
working code suitable for a fiction prop and for testing -- not audited
cryptography for high-value secrets.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

__all__ = [
    "PRIME",
    "RecoveryError",
    "Share",
    "split_secret",
    "combine_shares",
    "share_fingerprint",
    "serialize_shares",
    "parse_shares",
]

#: The prime field. 257 is prime and > 256, so every byte value fits.
PRIME = 257


class RecoveryError(ValueError):
    """Raised for secret-sharing misuse."""


@dataclass(frozen=True)
class Share:
    """One share: an x-coordinate and its y-values (one per secret byte)."""

    x: int
    y: Tuple[int, ...]

    def __post_init__(self) -> None:
        if not 1 <= self.x < PRIME:
            raise RecoveryError("share x must be in [1, 256]")


def _mod_inv(a: int, p: int) -> int:
    return pow(a, -1, p)


def _eval_poly(coeffs: Sequence[int], x: int, p: int) -> int:
    """Evaluate a polynomial at x mod p (Horner's method)."""
    result = 0
    for coeff in reversed(coeffs):
        result = (result * x + coeff) % p
    return result


def _lagrange(points: Sequence[Tuple[int, int]], x: int, p: int) -> int:
    """Lagrange interpolation of the points evaluated at x, mod p."""
    total = 0
    for i, (xi, yi) in enumerate(points):
        num = 1
        den = 1
        for j, (xj, _) in enumerate(points):
            if i == j:
                continue
            num = (num * (x - xj)) % p
            den = (den * (xi - xj)) % p
        total = (total + yi * num * _mod_inv(den, p)) % p
    return total


def split_secret(secret: bytes, n: int, k: int) -> List[Share]:
    """Split a secret into n shares with reconstruction threshold k.

    Args:
        secret: The bytes to protect (e.g. the disarm key).
        n: Total number of shares to produce (1..256).
        k: Minimum shares needed to reconstruct (2..n).

    Returns:
        A list of n Share objects. Any k of them reconstruct the secret.
    """
    if not secret:
        raise RecoveryError("secret must not be empty")
    if not 2 <= k <= n <= PRIME - 1:
        raise RecoveryError("need 2 <= k <= n <= 256")

    # One random polynomial per secret byte, shared across all x values.
    # (Generating a fresh polynomial per share would make the points lie on
    # different curves and reconstruction would fail.)
    polys: List[List[int]] = []
    for byte in secret:
        coeffs = [byte] + [secrets.randbelow(PRIME) for _ in range(k - 1)]
        polys.append(coeffs)

    shares: List[Share] = []
    for x in range(1, n + 1):
        ys = tuple(_eval_poly(coeffs, x, PRIME) for coeffs in polys)
        shares.append(Share(x=x, y=ys))
    return shares


def combine_shares(shares: Sequence[Share]) -> bytes:
    """Reconstruct the secret from at least k shares.

    Passing fewer than k shares returns garbage (by design -- Shamir gives
    no indication of insufficiency); the caller is responsible for holding
    enough shares. Duplicate x-coordinates are rejected.
    """
    if not shares:
        raise RecoveryError("no shares provided")
    xs = [s.x for s in shares]
    if len(xs) != len(set(xs)):
        raise RecoveryError("duplicate share x-coordinates")
    length = len(shares[0].y)
    if any(len(s.y) != length for s in shares):
        raise RecoveryError("shares have inconsistent lengths")

    secret = bytearray()
    for i in range(length):
        points = [(s.x, s.y[i]) for s in shares]
        # The reconstructed value lives in GF(257), i.e. 0..256. A correct
        # reconstruction of a real secret byte always lands in 0..255, so
        # clamping 256 -> 0 never alters a valid result; it only keeps an
        # under-threshold (garbage) reconstruction inside the byte range.
        secret.append(_lagrange(points, 0, PRIME) % 256)
    return bytes(secret)


def share_fingerprint(share: Share) -> str:
    """A short human-comparable fingerprint for one share.

    Lets friends confirm over the phone that they hold different shares
    without reading the share contents aloud.
    """
    import hashlib
    blob = f"{share.x}:{','.join(map(str, share.y))}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


def serialize_shares(shares: Sequence[Share]) -> str:
    """Serialize shares to a portable text format."""
    lines = ["dms-shares/1"]
    for share in shares:
        ys = ",".join(map(str, share.y))
        lines.append(f"{share.x}|{ys}")
    return "\n".join(lines)


def parse_shares(text: str) -> List[Share]:
    """Parse serialize_shares() output back into Share objects."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines or lines[0] != "dms-shares/1":
        raise RecoveryError("not a dms-shares/1 file")
    shares: List[Share] = []
    for line in lines[1:]:
        try:
            x_raw, ys_raw = line.split("|", 1)
            x = int(x_raw)
            y = tuple(int(v) for v in ys_raw.split(","))
        except ValueError as exc:
            raise RecoveryError(f"corrupt share line {line!r}") from exc
        shares.append(Share(x=x, y=y))
    return shares
