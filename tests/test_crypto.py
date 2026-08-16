"""Tests for deadman_switch.crypto -- authenticated heartbeats/cancels."""

from __future__ import annotations

import pytest

from deadman_switch.crypto import (
    CryptoError, derive_key, new_nonce, sign_cancel, sign_heartbeat,
    verify_cancel, verify_heartbeat,
)


def test_derive_key_deterministic_with_salt():
    key1, salt = derive_key("hunter2")
    key2, _ = derive_key("hunter2", salt=salt)
    assert key1 == key2
    assert len(key1) == 32


def test_derive_key_different_passphrase():
    key1, salt = derive_key("hunter2")
    key2, _ = derive_key("hunter3", salt=salt)
    assert key1 != key2


def test_derive_key_empty_rejected():
    with pytest.raises(CryptoError):
        derive_key("")


def test_heartbeat_roundtrip():
    key, _ = derive_key("secret")
    token = sign_heartbeat(key, counter=1, timestamp=1000.0)
    assert verify_heartbeat(key, token, last_counter=0) is True


def test_heartbeat_replay_rejected():
    key, _ = derive_key("secret")
    token = sign_heartbeat(key, counter=1, timestamp=1000.0)
    # Same counter again is a replay.
    assert verify_heartbeat(key, token, last_counter=1) is False


def test_heartbeat_wrong_key_rejected():
    key, _ = derive_key("secret")
    other, _ = derive_key("other")
    token = sign_heartbeat(key, counter=1, timestamp=1000.0)
    assert verify_heartbeat(other, token, last_counter=0) is False


def test_heartbeat_tampered_rejected():
    key, _ = derive_key("secret")
    token = sign_heartbeat(key, counter=1, timestamp=1000.0)
    token["counter"] = 999  # tamper
    assert verify_heartbeat(key, token, last_counter=0) is False


def test_heartbeat_negative_counter_rejected():
    key, _ = derive_key("secret")
    with pytest.raises(CryptoError):
        sign_heartbeat(key, counter=-1, timestamp=1000.0)


def test_cancel_roundtrip():
    key, _ = derive_key("secret")
    token = sign_cancel(key, "switch-a", timestamp=1000.0)
    assert verify_cancel(key, token, "switch-a") is True


def test_cancel_wrong_switch_rejected():
    key, _ = derive_key("secret")
    token = sign_cancel(key, "switch-a", timestamp=1000.0)
    assert verify_cancel(key, token, "switch-b") is False


def test_cancel_wrong_key_rejected():
    key, _ = derive_key("secret")
    other, _ = derive_key("other")
    token = sign_cancel(key, "switch-a", timestamp=1000.0)
    assert verify_cancel(other, token, "switch-a") is False


def test_cancel_empty_switch_rejected():
    key, _ = derive_key("secret")
    with pytest.raises(CryptoError):
        sign_cancel(key, "  ", timestamp=1000.0)


def test_nonce_unique():
    assert new_nonce() != new_nonce()


def test_heartbeat_token_has_mac():
    key, _ = derive_key("secret")
    token = sign_heartbeat(key, counter=1, timestamp=1000.0)
    assert "mac" in token
    assert token["kind"] == "heartbeat"
