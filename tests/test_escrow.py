"""Tests for deadman_switch.escrow -- encrypted payload escrow."""

from __future__ import annotations

import pytest

from deadman_switch.escrow import (
    EscrowError, EscrowRecord, release_payload, seal_payload,
)

# Low iterations for fast tests.
ITER = 1000


def test_seal_and_release_roundtrip():
    record = seal_payload("switch-1", "my last will", "passphrase",
                          iterations=ITER)
    assert release_payload(record, "passphrase") == "my last will"


def test_release_wrong_passphrase():
    record = seal_payload("switch-1", "secret", "right", iterations=ITER)
    with pytest.raises(EscrowError):
        release_payload(record, "wrong")


def test_release_switch_binding():
    record = seal_payload("switch-1", "secret", "pass", iterations=ITER)
    assert release_payload(record, "pass", switch_id="switch-1") == "secret"
    with pytest.raises(EscrowError):
        release_payload(record, "pass", switch_id="other-switch")


def test_tampered_ciphertext_detected():
    record = seal_payload("switch-1", "secret", "pass", iterations=ITER)
    tampered = bytearray(record.ciphertext)
    tampered[0] ^= 0xFF
    record.ciphertext = bytes(tampered)
    with pytest.raises(EscrowError):
        release_payload(record, "pass")


def test_tampered_mac_detected():
    record = seal_payload("switch-1", "secret", "pass", iterations=ITER)
    tampered = bytearray(record.mac)
    tampered[0] ^= 0xFF
    record.mac = bytes(tampered)
    with pytest.raises(EscrowError):
        release_payload(record, "pass")


def test_seal_validation():
    with pytest.raises(EscrowError):
        seal_payload("  ", "payload", "pass", iterations=ITER)
    with pytest.raises(EscrowError):
        seal_payload("s", "", "pass", iterations=ITER)
    with pytest.raises(EscrowError):
        seal_payload("s", "payload", "", iterations=ITER)


def test_dict_roundtrip():
    record = seal_payload("switch-1", "secret", "pass", iterations=ITER)
    restored = EscrowRecord.from_dict(record.to_dict())
    assert release_payload(restored, "pass") == "secret"


def test_from_dict_corrupt():
    with pytest.raises(EscrowError):
        EscrowRecord.from_dict({"switch_id": "s"})


def test_seal_is_randomized():
    a = seal_payload("s", "same", "pass", iterations=ITER)
    b = seal_payload("s", "same", "pass", iterations=ITER)
    # Fresh salt/nonce each time -> different ciphertext.
    assert a.ciphertext != b.ciphertext
    assert release_payload(a, "pass") == release_payload(b, "pass") == "same"


def test_unicode_payload():
    text = "última voluntad — 遺言 🕯"
    record = seal_payload("s", text, "pass", iterations=ITER)
    assert release_payload(record, "pass") == text
