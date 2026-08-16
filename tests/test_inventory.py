"""Tests for deadman_switch.inventory -- switch registry."""

from __future__ import annotations

import pytest

from deadman_switch.inventory import Inventory, InventoryError, SwitchRecord


def _inventory():
    inv = Inventory()
    inv.register(SwitchRecord("s1", "alice", armed_at=100.0))
    inv.register(SwitchRecord("s2", "bob", armed_at=200.0, template="travel"))
    inv.register(SwitchRecord("s3", "alice", armed_at=300.0))
    return inv


def test_record_validation():
    with pytest.raises(InventoryError):
        SwitchRecord("  ", "alice", 0.0)
    with pytest.raises(InventoryError):
        SwitchRecord("s", "  ", 0.0)


def test_register_duplicate():
    inv = _inventory()
    with pytest.raises(InventoryError):
        inv.register(SwitchRecord("s1", "x", 0.0))


def test_get_and_len():
    inv = _inventory()
    assert len(inv) == 3
    assert inv.get("s2").owner == "bob"
    with pytest.raises(InventoryError):
        inv.get("nope")


def test_active_and_retire():
    inv = _inventory()
    assert len(inv.active()) == 3
    inv.get("s1").retire(500.0)
    assert len(inv.active()) == 2
    assert len(inv.retired()) == 1


def test_retire_twice_raises():
    inv = _inventory()
    inv.get("s1").retire(500.0)
    with pytest.raises(InventoryError):
        inv.get("s1").retire(600.0)


def test_retire_before_arm_raises():
    inv = _inventory()
    with pytest.raises(InventoryError):
        inv.get("s1").retire(50.0)


def test_age():
    inv = _inventory()
    assert inv.get("s1").age(200.0) == 100.0
    inv.get("s1").retire(150.0)
    assert inv.get("s1").age(999.0) == 50.0  # capped at retirement


def test_owned_by():
    inv = _inventory()
    alice = inv.owned_by("alice")
    assert sorted(r.switch_id for r in alice) == ["s1", "s3"]


def test_stale():
    inv = _inventory()
    stale = inv.stale(now=1000.0, max_age_seconds=750.0)
    # s1 armed at 100 (age 900) and s2 at 200 (age 800) are stale.
    assert sorted(r.switch_id for r in stale) == ["s1", "s2"]


def test_stale_invalid():
    inv = _inventory()
    with pytest.raises(InventoryError):
        inv.stale(now=100.0, max_age_seconds=0)


def test_mark_fired():
    inv = _inventory()
    inv.mark_fired("s2")
    assert [r.switch_id for r in inv.fired()] == ["s2"]


def test_json_roundtrip():
    inv = _inventory()
    inv.get("s1").retire(500.0)
    inv.mark_fired("s2")
    restored = Inventory.from_json(inv.to_json())
    assert len(restored) == 3
    assert restored.get("s1").retired_at == 500.0
    assert restored.get("s2").fired is True


def test_from_json_corrupt():
    with pytest.raises(InventoryError):
        Inventory.from_json("{bad")


def test_record_from_dict_missing():
    with pytest.raises(InventoryError):
        SwitchRecord.from_dict({"switch_id": "s"})
