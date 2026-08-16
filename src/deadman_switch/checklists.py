"""Pre-arm safety checklists.

Arming a dead man's switch is a consequential act: a mistake in the setup
can fire a payload that cannot be unfired. This module encodes the
checklists a handler should walk through before arming, and scores how many
items are confirmed. It is the "preflight" for the switch.

Three checklists are provided:

* pre-arm      -- the essentials before the switch goes live.
* pre-travel   -- extra items when the operator is about to lose signal.
* pre-release  -- items to verify before a high-stakes payload is allowed
                  to fire.

Each item has an id, a prompt, and whether it is mandatory. The Checklist
object tracks confirmations and refuses to report "ready" while any
mandatory item is unchecked. Checklists are pure data, so they can be
rendered by the CLI, persisted, and tested.
"""

from __future__ import annotations

from typing import Dict, List, Optional

__all__ = [
    "ChecklistError",
    "ChecklistItem",
    "Checklist",
    "CHECKLISTS",
    "get_checklist",
]


class ChecklistError(ValueError):
    """Raised for checklist misuse."""


class ChecklistItem:
    """One item on a checklist."""

    def __init__(self, item_id: str, prompt: str,
                 mandatory: bool = True) -> None:
        if not item_id.strip():
            raise ChecklistError("item id must not be empty")
        if not prompt.strip():
            raise ChecklistError("prompt must not be empty")
        self.item_id = item_id.strip()
        self.prompt = prompt.strip()
        self.mandatory = mandatory

    def to_dict(self) -> Dict:
        return {"id": self.item_id, "prompt": self.prompt,
                "mandatory": self.mandatory}


class Checklist:
    """A named list of items with confirmation tracking."""

    def __init__(self, name: str, items: List[ChecklistItem],
                 description: str = "") -> None:
        if not name.strip():
            raise ChecklistError("checklist name must not be empty")
        if not items:
            raise ChecklistError("checklist must have at least one item")
        ids = [item.item_id for item in items]
        if len(ids) != len(set(ids)):
            raise ChecklistError("item ids must be distinct")
        self.name = name.strip()
        self.description = description.strip()
        self._items = list(items)
        self._confirmed: set = set()

    @property
    def items(self) -> List[ChecklistItem]:
        return list(self._items)

    def confirm(self, item_id: str) -> None:
        """Mark one item confirmed."""
        if not any(item.item_id == item_id for item in self._items):
            raise ChecklistError(f"unknown item {item_id!r}")
        self._confirmed.add(item_id)

    def unconfirm(self, item_id: str) -> None:
        """Remove a confirmation."""
        self._confirmed.discard(item_id)

    def is_confirmed(self, item_id: str) -> bool:
        return item_id in self._confirmed

    def pending(self) -> List[ChecklistItem]:
        """Items not yet confirmed."""
        return [item for item in self._items
                if item.item_id not in self._confirmed]

    def pending_mandatory(self) -> List[ChecklistItem]:
        """Mandatory items not yet confirmed."""
        return [item for item in self.pending() if item.mandatory]

    def ready(self) -> bool:
        """True once every mandatory item is confirmed."""
        return not self.pending_mandatory()

    def progress(self) -> Dict:
        """Counts of confirmed/total/mandatory-pending."""
        mandatory_total = sum(1 for item in self._items if item.mandatory)
        return {
            "total": len(self._items),
            "confirmed": len(self._confirmed),
            "mandatory_total": mandatory_total,
            "mandatory_pending": len(self.pending_mandatory()),
            "ready": self.ready(),
        }

    def render(self) -> str:
        """Render the checklist with confirmation marks."""
        lines = [f"# {self.name}"]
        if self.description:
            lines.append(self.description)
        lines.append("")
        for item in self._items:
            mark = "[x]" if item.item_id in self._confirmed else "[ ]"
            flag = "" if item.mandatory else " (optional)"
            lines.append(f"- {mark} {item.prompt}{flag}")
        return "\n".join(lines)


CHECKLISTS: Dict[str, Checklist] = {}


def _register(checklist: Checklist) -> None:
    CHECKLISTS[checklist.name] = checklist


_register(Checklist(
    name="pre-arm",
    description="Walk through before arming any switch.",
    items=[
        ChecklistItem("ttl", "TTL is sized for the operator's routine"),
        ChecklistItem("payload", "Payload reviewed and approved"),
        ChecklistItem("contacts", "At least one trusted contact is set"),
        ChecklistItem("cancel", "Cancel token/key is stored safely"),
        ChecklistItem("drill", "Operator has rehearsed beat and cancel"),
        ChecklistItem("audit", "Config audit shows no critical findings"),
        ChecklistItem("heartbeat-path", "Heartbeat path is stable and private",
                      mandatory=False),
    ],
))

_register(Checklist(
    name="pre-travel",
    description="Extra items before the operator loses signal.",
    items=[
        ChecklistItem("ttl-extended", "TTL extended to cover the journey"),
        ChecklistItem("schedule", "Beat schedule shared with the handler"),
        ChecklistItem("out-of-band", "Out-of-band contact channel agreed"),
        ChecklistItem("duress", "Duress code reviewed with the operator"),
        ChecklistItem("roaming", "Device roaming/offline behavior checked",
                      mandatory=False),
    ],
))

_register(Checklist(
    name="pre-release",
    description="Verify before a high-stakes payload may fire.",
    items=[
        ChecklistItem("quorum", "Cancel quorum is configured"),
        ChecklistItem("escrow", "Sensitive payload is in escrow, not config"),
        ChecklistItem("recovery", "Disarm key is split among trusted parties"),
        ChecklistItem("postmortem", "Post-mortem plan is written"),
        ChecklistItem("legal", "Payload consequences reviewed",
                      mandatory=False),
    ],
))


def get_checklist(name: str) -> Checklist:
    """Fetch a fresh (unconfirmed) copy of a named checklist."""
    if name not in CHECKLISTS:
        raise ChecklistError(
            f"unknown checklist {name!r}; choose from {sorted(CHECKLISTS)}")
    template = CHECKLISTS[name]
    return Checklist(name=template.name,
                     items=[ChecklistItem(i.item_id, i.prompt, i.mandatory)
                            for i in template.items],
                     description=template.description)
