"""Tests for deadman_switch.quorum -- multi-party cancel approval."""

from __future__ import annotations

import pytest

from deadman_switch.quorum import Approval, Quorum, QuorumError

PARTIES = ["alice", "bob", "carol"]


def _quorum(threshold=2):
    return Quorum("switch-a", threshold, PARTIES)


def test_validation():
    with pytest.raises(QuorumError):
        Quorum("  ", 2, PARTIES)
    with pytest.raises(QuorumError):
        Quorum("s", 0, PARTIES)
    with pytest.raises(QuorumError):
        Quorum("s", 5, PARTIES)  # threshold > parties
    with pytest.raises(QuorumError):
        Quorum("s", 2, ["a", "a"])  # duplicate parties


def test_approval_validation():
    with pytest.raises(QuorumError):
        Approval("  ", "s", 0)
    with pytest.raises(QuorumError):
        Approval("a", "  ", 0)
    with pytest.raises(QuorumError):
        Approval("a", "s", -1)


def test_quorum_met_at_threshold():
    q = _quorum(threshold=2)
    q.begin_round()
    assert q.cast(Approval("alice", "switch-a", q.round)) is False
    assert q.cast(Approval("bob", "switch-a", q.round)) is True
    assert q.is_met() is True


def test_quorum_not_met_below_threshold():
    q = _quorum(threshold=3)
    q.begin_round()
    q.cast(Approval("alice", "switch-a", q.round))
    q.cast(Approval("bob", "switch-a", q.round))
    assert q.is_met() is False
    assert q.remaining() == 1


def test_wrong_switch_rejected():
    q = _quorum(threshold=1)
    q.begin_round()
    assert q.cast(Approval("alice", "other-switch", q.round)) is False
    assert q.is_met() is False


def test_wrong_round_rejected():
    q = _quorum(threshold=1)
    q.begin_round()
    assert q.cast(Approval("alice", "switch-a", q.round + 5)) is False
    assert q.is_met() is False


def test_unknown_party_rejected():
    q = _quorum(threshold=1)
    q.begin_round()
    assert q.cast(Approval("mallory", "switch-a", q.round)) is False


def test_invalid_approval_rejected():
    q = _quorum(threshold=1)
    q.begin_round()
    assert q.cast(Approval("alice", "switch-a", q.round, valid=False)) is False
    assert q.is_met() is False


def test_duplicate_approval_ignored():
    q = _quorum(threshold=2)
    q.begin_round()
    q.cast(Approval("alice", "switch-a", q.round))
    q.cast(Approval("alice", "switch-a", q.round))  # dup
    assert len(q.approved_parties) == 1
    assert q.is_met() is False


def test_begin_round_clears():
    q = _quorum(threshold=2)
    q.begin_round()
    q.cast(Approval("alice", "switch-a", q.round))
    new_round = q.begin_round()
    assert q.approved_parties == set()
    assert new_round == 2
    # Old-round approval now rejected.
    assert q.cast(Approval("alice", "switch-a", 1)) is False


def test_status():
    q = _quorum(threshold=2)
    q.begin_round()
    q.cast(Approval("alice", "switch-a", q.round))
    s = q.status()
    assert s["approved"] == ["alice"]
    assert s["remaining"] == 1
    assert s["met"] is False
    assert s["threshold"] == 2


def test_rejected_recorded():
    q = _quorum(threshold=1)
    q.begin_round()
    q.cast(Approval("mallory", "switch-a", q.round))
    assert len(q.rejected) == 1
