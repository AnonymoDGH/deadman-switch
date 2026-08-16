"""Authenticated heartbeats and cancel tokens.

A plain heartbeat file has a fatal flaw: anyone who can touch the file can
keep the switch alive forever, defeating the whole point. This module fixes
that with HMAC authentication.

* A heartbeat is no longer just a file touch -- it is a signed token
  (timestamp + counter + HMAC) that only someone holding the secret key can
  produce. The switch verifies the signature before accepting the beat.
* A cancel (authenticated abort from the TRIPPED state) likewise requires a
  signed token, so an attacker who trips the switch cannot also cancel it.

Everything is stdlib HMAC-SHA256. Keys are derived from a passphrase with
PBKDF2 so a human-memorable secret can seed the whole scheme.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Dict, Optional, Tuple

__all__ = [
    "CryptoError",
    "derive_key",
    "sign_heartbeat",
    "verify_heartbeat",
    "sign_cancel",
    "verify_cancel",
    "new_nonce",
]

_KDF_ITERATIONS = 100_000
_KEY_BYTES = 32


class CryptoError(ValueError):
    """Raised for authentication failures or misuse."""


def derive_key(passphrase: str, salt: Optional[bytes] = None,
               iterations: int = _KDF_ITERATIONS) -> Tuple[bytes, bytes]:
    """Derive a 32-byte key from a passphrase. Returns (key, salt)."""
    if not passphrase:
        raise CryptoError("passphrase must not be empty")
    salt = salt or os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"),
                              salt, iterations, dklen=_KEY_BYTES)
    return key, salt


def _mac(key: bytes, payload: Dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(key, canonical.encode("utf-8"), "sha256").hexdigest()


def new_nonce() -> str:
    """A fresh random nonce for replay protection."""
    return os.urandom(16).hex()


def sign_heartbeat(key: bytes, counter: int, timestamp: float,
                   nonce: Optional[str] = None) -> Dict:
    """Produce a signed heartbeat token.

    The token binds the counter (monotonic, defeats replay of old beats)
    and the timestamp together under the key.
    """
    if counter < 0:
        raise CryptoError("counter must be >= 0")
    nonce = nonce or new_nonce()
    payload = {"counter": counter, "ts": timestamp, "nonce": nonce,
               "kind": "heartbeat"}
    token = dict(payload)
    token["mac"] = _mac(key, payload)
    return token


def verify_heartbeat(key: bytes, token: Dict,
                     last_counter: int = -1) -> bool:
    """Verify a heartbeat token's signature and freshness.

    Returns True only if the MAC is valid AND the counter is strictly
    greater than last_counter (replay protection).
    """
    payload = {k: token.get(k) for k in ("counter", "ts", "nonce", "kind")}
    if payload.get("kind") != "heartbeat":
        return False
    expected = _mac(key, payload)
    if not hmac.compare_digest(expected, str(token.get("mac", ""))):
        return False
    counter = token.get("counter", -1)
    return counter > last_counter


def sign_cancel(key: bytes, switch_id: str, timestamp: float,
                nonce: Optional[str] = None) -> Dict:
    """Produce a signed cancel token bound to a specific switch."""
    if not switch_id.strip():
        raise CryptoError("switch_id must not be empty")
    nonce = nonce or new_nonce()
    payload = {"switch_id": switch_id, "ts": timestamp, "nonce": nonce,
               "kind": "cancel"}
    token = dict(payload)
    token["mac"] = _mac(key, payload)
    return token


def verify_cancel(key: bytes, token: Dict, switch_id: str) -> bool:
    """Verify a cancel token is authentic and bound to this switch."""
    payload = {k: token.get(k) for k in ("switch_id", "ts", "nonce", "kind")}
    if payload.get("kind") != "cancel":
        return False
    if payload.get("switch_id") != switch_id:
        return False
    expected = _mac(key, payload)
    return hmac.compare_digest(expected, str(token.get("mac", "")))
