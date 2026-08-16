"""Encrypted payload escrow.

Some payloads are too sensitive to sit in the config file in the clear --
a last-will document, a password list, a confession. This module stores such
payloads in escrow: encrypted at rest with a key derived from a passphrase,
and only decryptable when the switch actually fires.

The escrow record binds the ciphertext to the switch id and a release
counter, so a ciphertext captured from one switch cannot be replayed
against another. Decryption requires the passphrase; there is no backdoor.
The implementation uses PBKDF2-HMAC-SHA256 for key derivation and
AES-CTR-style keystream via SHA-256 in counter mode with an HMAC for
integrity -- pure stdlib, suitable for a fiction prop and for testing.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Dict, Optional, Tuple

__all__ = [
    "EscrowError",
    "EscrowRecord",
    "seal_payload",
    "release_payload",
    "KDF_ITERATIONS",
]

#: PBKDF2 iterations. Tests may lower this via the iterations argument.
KDF_ITERATIONS = 100_000

MAGIC = b"DMS-ESCROW-V1"


class EscrowError(ValueError):
    """Raised for escrow misuse or failed decryption."""


def _derive_key(passphrase: str, salt: bytes,
                iterations: int = KDF_ITERATIONS) -> bytes:
    if not passphrase:
        raise EscrowError("passphrase must not be empty")
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"),
                               salt, iterations, dklen=64)


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """SHA-256 counter-mode keystream of the requested length."""
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


class EscrowRecord:
    """One sealed payload, stored as a dict."""

    def __init__(self, switch_id: str, salt: bytes, nonce: bytes,
                 ciphertext: bytes, mac: bytes, iterations: int) -> None:
        self.switch_id = switch_id
        self.salt = salt
        self.nonce = nonce
        self.ciphertext = ciphertext
        self.mac = mac
        self.iterations = iterations

    def to_dict(self) -> Dict:
        return {
            "switch_id": self.switch_id,
            "salt": self.salt.hex(),
            "nonce": self.nonce.hex(),
            "ciphertext": self.ciphertext.hex(),
            "mac": self.mac.hex(),
            "iterations": self.iterations,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "EscrowRecord":
        try:
            return cls(
                switch_id=data["switch_id"],
                salt=bytes.fromhex(data["salt"]),
                nonce=bytes.fromhex(data["nonce"]),
                ciphertext=bytes.fromhex(data["ciphertext"]),
                mac=bytes.fromhex(data["mac"]),
                iterations=data["iterations"],
            )
        except (KeyError, ValueError) as exc:
            raise EscrowError(f"corrupt escrow record: {exc}") from exc


def seal_payload(switch_id: str, payload_text: str, passphrase: str,
                 iterations: int = KDF_ITERATIONS) -> EscrowRecord:
    """Encrypt a payload into escrow.

    The plaintext is bound to the switch id so it cannot be moved between
    switches. Returns an EscrowRecord safe to store.
    """
    if not switch_id.strip():
        raise EscrowError("switch_id must not be empty")
    if not payload_text:
        raise EscrowError("payload_text must not be empty")

    salt = os.urandom(16)
    nonce = os.urandom(16)
    key = _derive_key(passphrase, salt, iterations)
    enc_key, mac_key = key[:32], key[32:]

    plaintext = json.dumps({"switch_id": switch_id,
                            "payload": payload_text},
                           sort_keys=True).encode("utf-8")
    stream = _keystream(enc_key, nonce, len(plaintext))
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream))
    mac = hmac.new(mac_key, MAGIC + switch_id.encode("utf-8") + ciphertext,
                   "sha256").digest()
    return EscrowRecord(switch_id, salt, nonce, ciphertext, mac, iterations)


def release_payload(record: EscrowRecord, passphrase: str,
                    switch_id: Optional[str] = None) -> str:
    """Decrypt an escrowed payload.

    Args:
        record: The sealed record.
        passphrase: The passphrase used at seal time.
        switch_id: If given, the record must belong to this switch.

    Returns:
        The original payload text.

    Raises:
        EscrowError: On wrong passphrase, tampering, or switch mismatch.
    """
    if switch_id is not None and record.switch_id != switch_id:
        raise EscrowError("escrow record belongs to a different switch")

    key = _derive_key(passphrase, record.salt, record.iterations)
    enc_key, mac_key = key[:32], key[32:]

    expected_mac = hmac.new(mac_key,
                            MAGIC + record.switch_id.encode("utf-8")
                            + record.ciphertext, "sha256").digest()
    if not hmac.compare_digest(expected_mac, record.mac):
        raise EscrowError("escrow integrity check failed "
                          "(wrong passphrase or tampered record)")

    stream = _keystream(enc_key, record.nonce, len(record.ciphertext))
    plaintext = bytes(a ^ b for a, b in zip(record.ciphertext, stream))
    try:
        data = json.loads(plaintext.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise EscrowError("escrow payload corrupted") from exc
    if data.get("switch_id") != record.switch_id:
        raise EscrowError("escrow payload switch binding mismatch")
    return data["payload"]
