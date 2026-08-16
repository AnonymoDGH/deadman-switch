"""Trusted contact roster.

A switch that fires into the void is useless; someone has to receive the
alert and know what to do. This module manages the roster of trusted
contacts: who they are, how to reach them, what they are cleared to know,
and how to rotate through them so no single contact is a point of failure.

Each contact has a reachability priority and a clearance level. The roster
can produce an ordered notification list (who to alert first), rotate the
primary contact on a schedule, and validate that the roster is deep enough
to survive losing any one member. Everything is pure data manipulation, so
it is deterministic and easy to test.
"""

from __future__ import annotations

from typing import Dict, List, Optional

__all__ = [
    "ContactError",
    "Contact",
    "Roster",
]

CLEARANCE_LEVELS = ("none", "alert-only", "full")


class ContactError(ValueError):
    """Raised for roster misuse."""


class Contact:
    """One trusted contact."""

    def __init__(self, name: str, channel: str, priority: int = 100,
                 clearance: str = "alert-only", note: str = "") -> None:
        if not name.strip():
            raise ContactError("contact name must not be empty")
        if not channel.strip():
            raise ContactError("contact channel must not be empty")
        if clearance not in CLEARANCE_LEVELS:
            raise ContactError(
                f"clearance must be one of {CLEARANCE_LEVELS}")
        if priority < 0:
            raise ContactError("priority must be >= 0")
        self.name = name.strip()
        self.channel = channel.strip()
        self.priority = priority
        self.clearance = clearance
        self.note = note

    def to_dict(self) -> Dict:
        return {"name": self.name, "channel": self.channel,
                "priority": self.priority, "clearance": self.clearance,
                "note": self.note}

    @classmethod
    def from_dict(cls, data: Dict) -> "Contact":
        try:
            return cls(name=data["name"], channel=data["channel"],
                       priority=data.get("priority", 100),
                       clearance=data.get("clearance", "alert-only"),
                       note=data.get("note", ""))
        except KeyError as exc:
            raise ContactError(f"contact missing field {exc}") from exc

    def __repr__(self) -> str:
        return (f"Contact({self.name!r}, {self.channel!r}, "
                f"priority={self.priority}, clearance={self.clearance!r})")


class Roster:
    """An ordered set of trusted contacts."""

    def __init__(self, contacts: Optional[List[Contact]] = None) -> None:
        self._contacts: List[Contact] = []
        for contact in contacts or []:
            self.add(contact)

    def add(self, contact: Contact) -> None:
        if any(c.name == contact.name for c in self._contacts):
            raise ContactError(f"contact {contact.name!r} already exists")
        self._contacts.append(contact)

    def remove(self, name: str) -> None:
        self._contacts = [c for c in self._contacts if c.name != name]

    def get(self, name: str) -> Contact:
        for contact in self._contacts:
            if contact.name == name:
                return contact
        raise ContactError(f"no contact named {name!r}")

    def __len__(self) -> int:
        return len(self._contacts)

    def names(self) -> List[str]:
        return [c.name for c in self._contacts]

    def notification_order(self) -> List[Contact]:
        """Contacts sorted by priority (lowest number first)."""
        return sorted(self._contacts, key=lambda c: c.priority)

    def primary(self) -> Optional[Contact]:
        """The highest-priority contact, if any."""
        order = self.notification_order()
        return order[0] if order else None

    def cleared(self, level: str) -> List[Contact]:
        """Contacts at or above a clearance level."""
        if level not in CLEARANCE_LEVELS:
            raise ContactError(f"unknown clearance {level!r}")
        rank = CLEARANCE_LEVELS.index(level)
        return [c for c in self.notification_order()
                if CLEARANCE_LEVELS.index(c.clearance) >= rank]

    def rotate(self, steps: int = 1) -> None:
        """Rotate the priority order by moving the head to the tail.

        Repeated rotation cycles the primary contact so no one person is
        always first.
        """
        if not self._contacts:
            return
        order = self.notification_order()
        steps = steps % len(order)
        rotated = order[steps:] + order[:steps]
        # Reassign priorities to match the rotated order.
        for index, contact in enumerate(rotated):
            contact.priority = index

    def redundancy_ok(self, required: int = 2) -> bool:
        """True if the roster can lose one contact and still meet required."""
        return len(self._contacts) - 1 >= required

    def to_list(self) -> List[Dict]:
        return [c.to_dict() for c in self.notification_order()]

    @classmethod
    def from_list(cls, data: List[Dict]) -> "Roster":
        return cls([Contact.from_dict(d) for d in data])
