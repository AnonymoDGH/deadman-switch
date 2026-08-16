"""Tests for deadman_switch.recovery -- Shamir secret sharing."""

from __future__ import annotations

import pytest

from deadman_switch.recovery import (
    PRIME, RecoveryError, Share, combine_shares, parse_shares,
    serialize_shares, share_fingerprint, split_secret,
)


SECRET = b"disarm-key-0123456789"


def test_split_and_combine_full():
    shares = split_secret(SECRET, n=5, k=3)
    assert len(shares) == 5
    assert combine_shares(shares) == SECRET


def test_combine_threshold_subset():
    shares = split_secret(SECRET, n=5, k=3)
    # Any 3 shares reconstruct.
    assert combine_shares(shares[:3]) == SECRET
    assert combine_shares(shares[2:]) == SECRET
    assert combine_shares([shares[0], shares[2], shares[4]]) == SECRET


def test_combine_two_of_three_threshold():
    shares = split_secret(SECRET, n=3, k=2)
    assert combine_shares(shares[:2]) == SECRET


def test_insufficient_shares_give_wrong_result():
    shares = split_secret(SECRET, n=5, k=3)
    # Only 2 of a 3-threshold: result differs (no error, by design).
    wrong = combine_shares(shares[:2])
    assert wrong != SECRET


def test_split_validation():
    with pytest.raises(RecoveryError):
        split_secret(b"", n=3, k=2)
    with pytest.raises(RecoveryError):
        split_secret(SECRET, n=3, k=1)   # k must be >= 2
    with pytest.raises(RecoveryError):
        split_secret(SECRET, n=2, k=3)   # k > n
    with pytest.raises(RecoveryError):
        split_secret(SECRET, n=300, k=2)  # n too large


def test_combine_empty_raises():
    with pytest.raises(RecoveryError):
        combine_shares([])


def test_combine_duplicate_x_raises():
    shares = split_secret(SECRET, n=3, k=2)
    dup = Share(x=shares[0].x, y=shares[1].y)
    with pytest.raises(RecoveryError):
        combine_shares([shares[0], dup])


def test_combine_inconsistent_length_raises():
    shares = split_secret(SECRET, n=3, k=2)
    short = Share(x=99, y=shares[0].y[:-1])
    with pytest.raises(RecoveryError):
        combine_shares([shares[0], short])


def test_share_x_validation():
    with pytest.raises(RecoveryError):
        Share(x=0, y=(1,))
    with pytest.raises(RecoveryError):
        Share(x=PRIME, y=(1,))


def test_fingerprint_stable_and_distinct():
    shares = split_secret(SECRET, n=3, k=2)
    assert share_fingerprint(shares[0]) == share_fingerprint(shares[0])
    assert share_fingerprint(shares[0]) != share_fingerprint(shares[1])


def test_serialize_parse_roundtrip():
    shares = split_secret(SECRET, n=4, k=2)
    text = serialize_shares(shares)
    restored = parse_shares(text)
    assert restored == shares
    assert combine_shares(restored[:2]) == SECRET


def test_parse_bad_header():
    with pytest.raises(RecoveryError):
        parse_shares("wrong-header\n1|2,3")


def test_parse_corrupt_line():
    with pytest.raises(RecoveryError):
        parse_shares("dms-shares/1\nnot|a|number")


def test_single_byte_secret():
    shares = split_secret(b"\x42", n=3, k=2)
    assert combine_shares(shares[:2]) == b"\x42"
