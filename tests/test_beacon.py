"""Tests for deadman_switch.beacon -- signed liveness beacons."""

from __future__ import annotations

import pytest

from deadman_switch.beacon import (
    Beacon, BeaconError, BeaconWatcher, sign_beacon, verify_beacon,
)

KEY = b"0123456789abcdef0123456789abcdef"


def test_sign_and_verify():
    beacon = sign_beacon(KEY, "switch-a", seq=1, ts=1000.0)
    assert verify_beacon(KEY, beacon) is True


def test_verify_wrong_key():
    beacon = sign_beacon(KEY, "switch-a", seq=1, ts=1000.0)
    assert verify_beacon(b"other-key", beacon) is False


def test_verify_tampered():
    beacon = sign_beacon(KEY, "switch-a", seq=1, ts=1000.0)
    beacon.seq = 999
    assert verify_beacon(KEY, beacon) is False


def test_beacon_validation():
    with pytest.raises(BeaconError):
        Beacon("  ", 0, 0.0, "mac")
    with pytest.raises(BeaconError):
        Beacon("s", -1, 0.0, "mac")


def test_beacon_json_roundtrip():
    beacon = sign_beacon(KEY, "switch-a", seq=3, ts=1000.0)
    restored = Beacon.from_json(beacon.to_json())
    assert restored.to_dict() == beacon.to_dict()
    assert verify_beacon(KEY, restored) is True


def test_beacon_from_json_corrupt():
    with pytest.raises(BeaconError):
        Beacon.from_json("{not json")


def test_beacon_from_dict_missing_field():
    with pytest.raises(BeaconError):
        Beacon.from_dict({"switch_id": "s", "seq": 1})


def test_watcher_accepts_fresh():
    watcher = BeaconWatcher(KEY, "switch-a")
    assert watcher.receive(sign_beacon(KEY, "switch-a", 1, 1000.0)) is True
    assert watcher.accepted == 1
    assert watcher.last_seq == 1


def test_watcher_rejects_replay():
    watcher = BeaconWatcher(KEY, "switch-a")
    watcher.receive(sign_beacon(KEY, "switch-a", 5, 1000.0))
    assert watcher.receive(sign_beacon(KEY, "switch-a", 5, 1001.0)) is False
    assert watcher.receive(sign_beacon(KEY, "switch-a", 3, 1002.0)) is False
    assert watcher.rejected == 2


def test_watcher_rejects_forgery():
    watcher = BeaconWatcher(KEY, "switch-a")
    forged = sign_beacon(b"wrong-key", "switch-a", 1, 1000.0)
    assert watcher.receive(forged) is False
    assert watcher.rejected == 1


def test_watcher_rejects_wrong_switch():
    watcher = BeaconWatcher(KEY, "switch-a")
    assert watcher.receive(sign_beacon(KEY, "switch-b", 1, 1000.0)) is False


def test_watcher_is_overdue():
    watcher = BeaconWatcher(KEY, "switch-a")
    assert watcher.is_overdue(now=1000.0, max_age=60) is True  # never heard
    watcher.receive(sign_beacon(KEY, "switch-a", 1, 1000.0))
    assert watcher.is_overdue(now=1030.0, max_age=60) is False
    assert watcher.is_overdue(now=1061.0, max_age=60) is True


def test_watcher_last_ts():
    watcher = BeaconWatcher(KEY, "switch-a")
    assert watcher.last_ts is None
    watcher.receive(sign_beacon(KEY, "switch-a", 1, 1234.0))
    assert watcher.last_ts == 1234.0
