"""Switch inventory registry.

An organization may run many switches across operators and missions. The
forgotten-switch scenario happens because nobody kept an inventory. This
module is that inventory: a registry of every switch with its lifecycle
metadata -- who owns it, when it was armed, what template it came from, and
whether it is still active.

The registry answers the questions a supervisor asks: which switches are
armed right now? which have been armed longer than their review period?
which fired and need a debrief? It is pure data with JSON serialization, so
it can be persisted and audited.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

__all__ = ["InventoryError", "SwitchRecord", "Inventory"]


class InventoryError(ValueError):
    """Raised for inventory misuse."""


class SwitchRecord:
    """Lifecycle metadata for one switch."""

    def __init__(self, switch_id: str, owner: str, armed_at: float,
                 template: str = "custom", note: str = "") -> None:
        if not switch_id.strip():
            raise InventoryError("switch_id must not be empty")
        if not owner.strip():
            raise InventoryError("owner must not be empty")
        self.switch_id = switch_id.strip()
        self.owner = owner.strip()
        self.armed_at = armed_at
        self.template = template
        self.note = note
        self.retired_at: Optional[float] = None
        self.fired = False

    @property
    def active(self) -> bool:
        """True while the switch has not been retired."""
        return self.retired_at is None

    def retire(self, at: float) -> None:
        if not self.active:
            raise InventoryError(f"{self.switch_id} already retired")
        if at < self.armed_at:
            raise InventoryError("cannot retire before arming")
        self.retired_at = at

    def age(self, now: float) -> float:
        """Seconds since arming (to now, or to retirement)."""
        end = self.retired_at if self.retired_at is not None else now
        return max(0.0, end - self.armed_at)

    def to_dict(self) -> Dict:
        return {"switch_id": self.switch_id, "owner": self.owner,
                "armed_at": self.armed_at, "template": self.template,
                "note": self.note, "retired_at": self.retired_at,
                "fired": self.fired}

    @classmethod
    def from_dict(cls, data: Dict) -> "SwitchRecord":
        try:
            record = cls(switch_id=data["switch_id"], owner=data["owner"],
                         armed_at=data["armed_at"],
                         template=data.get("template", "custom"),
                         note=data.get("note", ""))
        except KeyError as exc:
            raise InventoryError(f"record missing field {exc}") from exc
        record.retired_at = data.get("retired_at")
        record.fired = data.get("fired", False)
        return record


class Inventory:
    """The registry of all switches."""

    def __init__(self) -> None:
        self._records: Dict[str, SwitchRecord] = {}

    def register(self, record: SwitchRecord) -> None:
        if record.switch_id in self._records:
            raise InventoryError(
                f"switch {record.switch_id!r} already registered")
        self._records[record.switch_id] = record

    def get(self, switch_id: str) -> SwitchRecord:
        if switch_id not in self._records:
            raise InventoryError(f"no switch {switch_id!r} in inventory")
        return self._records[switch_id]

    def __len__(self) -> int:
        return len(self._records)

    def ids(self) -> List[str]:
        return sorted(self._records)

    def active(self) -> List[SwitchRecord]:
        """All switches not yet retired, oldest first."""
        return sorted((r for r in self._records.values() if r.active),
                      key=lambda r: r.armed_at)

    def retired(self) -> List[SwitchRecord]:
        return sorted((r for r in self._records.values() if not r.active),
                      key=lambda r: r.retired_at or 0.0)

    def fired(self) -> List[SwitchRecord]:
        """Switches that fired and need a debrief."""
        return [r for r in self._records.values() if r.fired]

    def owned_by(self, owner: str) -> List[SwitchRecord]:
        return [r for r in self._records.values() if r.owner == owner]

    def stale(self, now: float, max_age_seconds: float) -> List[SwitchRecord]:
        """Active switches armed longer than max_age_seconds.

        These are the forgotten-switch candidates that need review.
        """
        if max_age_seconds <= 0:
            raise InventoryError("max_age_seconds must be positive")
        return [r for r in self.active()
                if r.age(now) > max_age_seconds]

    def mark_fired(self, switch_id: str) -> None:
        self.get(switch_id).fired = True

    def to_json(self) -> str:
        return json.dumps([r.to_dict() for r in
                          sorted(self._records.values(),
                                 key=lambda r: r.armed_at)],
                          indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "Inventory":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InventoryError(f"corrupt inventory: {exc}") from exc
        inventory = cls()
        for item in data:
            inventory.register(SwitchRecord.from_dict(item))
        return inventory
