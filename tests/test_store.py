"""Tests for deadman_switch.store -- persistent switch storage."""

from __future__ import annotations

import pytest

from deadman_switch.events import EventLog
from deadman_switch.store import StoreError, SwitchStore


def _state():
    return {"state": "armed", "last_beat": 1234.0, "ttl_seconds": 60}


def _log():
    log = EventLog()
    log.append("arm", {"ttl": 60}, at=1.0)
    log.append("beat", at=2.0)
    return log


def test_save_and_load_roundtrip(tmp_path):
    store = SwitchStore(tmp_path / "s")
    store.save(_state(), _log())
    loaded = store.load()
    assert loaded["state"] == _state()
    assert len(loaded["log"]) == 2
    assert loaded["log"].verify() is True


def test_exists(tmp_path):
    store = SwitchStore(tmp_path / "s")
    assert store.exists() is False
    store.save(_state(), _log())
    assert store.exists() is True


def test_load_missing_raises(tmp_path):
    store = SwitchStore(tmp_path / "nope")
    with pytest.raises(StoreError):
        store.load()


def test_load_tampered_log_raises(tmp_path):
    store = SwitchStore(tmp_path / "s")
    store.save(_state(), _log())
    # Tamper with the event log on disk.
    text = store.events_path.read_text(encoding="utf-8")
    store.events_path.write_text(text.replace('"beat"', '"BEAT"'),
                                 encoding="utf-8")
    with pytest.raises(StoreError, match="tampered"):
        store.load(verify_chain=True)


def test_load_tampered_ok_if_unverified(tmp_path):
    store = SwitchStore(tmp_path / "s")
    store.save(_state(), _log())
    text = store.events_path.read_text(encoding="utf-8")
    store.events_path.write_text(text.replace('"beat"', '"BEAT"'),
                                 encoding="utf-8")
    loaded = store.load(verify_chain=False)
    assert loaded["log"].verify() is False


def test_load_state_only(tmp_path):
    store = SwitchStore(tmp_path / "s")
    store.save(_state(), _log())
    state = store.load_state_only()
    assert state["state"] == "armed"


def test_load_state_only_missing_raises(tmp_path):
    store = SwitchStore(tmp_path / "nope")
    with pytest.raises(StoreError):
        store.load_state_only()


def test_clear(tmp_path):
    store = SwitchStore(tmp_path / "s")
    store.save(_state(), _log())
    store.clear()
    assert store.exists() is False
    assert not store.events_path.exists()


def test_corrupt_switch_file_raises(tmp_path):
    store = SwitchStore(tmp_path / "s")
    store.directory.mkdir(parents=True)
    store.switch_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(StoreError, match="corrupt"):
        store.load()


def test_atomic_write_leaves_no_tmp(tmp_path):
    store = SwitchStore(tmp_path / "s")
    store.save(_state(), _log())
    tmps = list(store.directory.glob("*.tmp"))
    assert tmps == []
