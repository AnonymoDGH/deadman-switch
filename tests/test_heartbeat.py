"""Tests for deadman_switch.heartbeat -- signed heartbeat records."""

from __future__ import annotations

import pytest

from deadman_switch.heartbeat import (
    HeartbeatError, HeartbeatLedger, HeartbeatRecord, sign_heartbeat_record,
    verify_heartbeat_record,
)

KEY = b"0123456789abcdef0123456789abcdef"


def test_sign_and_verify():
    record = sign_heartbeat_record(KEY, seq=1, ts=1000.0, note="all good")
    assert verify_heartbeat_record(KEY, record) is True


def test_verify_wrong_key():
    record = sign_heartbeat_record(KEY, seq=1, ts=1000.0)
    assert verify_heartbeat_record(b"other", record) is False


def test_verify_tampered_note():
    record = sign_heartbeat_record(KEY, seq=1, ts=1000.0, note="fine")
    record.note = "tampered"
    assert verify_heartbeat_record(KEY, record) is False


def test_record_validation():
    with pytest.raises(HeartbeatError):
        HeartbeatRecord(seq=-1, ts=0.0)


def test_json_roundtrip():
    record = sign_heartbeat_record(KEY, seq=5, ts=1000.0, note="ok")
    restored = HeartbeatRecord.from_json(record.to_json())
    assert restored.to_dict() == record.to_dict()
    assert verify_heartbeat_record(KEY, restored) is True


def test_from_json_corrupt():
    with pytest.raises(HeartbeatError):
        HeartbeatRecord.from_json("{bad")


def test_from_dict_missing():
    with pytest.raises(HeartbeatError):
        HeartbeatRecord.from_dict({"seq": 1})


def test_ledger_accepts_fresh():
    ledger = HeartbeatLedger(KEY)
    assert ledger.accept(sign_heartbeat_record(KEY, 1, 1000.0)) is True
    assert ledger.last_seq == 1
    assert len(ledger.records) == 1


def test_ledger_rejects_replay():
    ledger = HeartbeatLedger(KEY)
    ledger.accept(sign_heartbeat_record(KEY, 5, 1000.0))
    assert ledger.accept(sign_heartbeat_record(KEY, 5, 1001.0)) is False
    assert ledger.accept(sign_heartbeat_record(KEY, 3, 1002.0)) is False
    assert ledger.rejected == 2


def test_ledger_rejects_forgery():
    ledger = HeartbeatLedger(KEY)
    forged = sign_heartbeat_record(b"wrong", 1, 1000.0)
    assert ledger.accept(forged) is False
    assert ledger.rejected == 1


def test_ledger_beat_times():
    ledger = HeartbeatLedger(KEY)
    ledger.accept(sign_heartbeat_record(KEY, 1, 1000.0))
    ledger.accept(sign_heartbeat_record(KEY, 2, 1030.0))
    assert ledger.beat_times() == [1000.0, 1030.0]


def test_ledger_latest_note():
    ledger = HeartbeatLedger(KEY)
    assert ledger.latest_note() is None
    ledger.accept(sign_heartbeat_record(KEY, 1, 1000.0, note="safe"))
    assert ledger.latest_note() == "safe"
