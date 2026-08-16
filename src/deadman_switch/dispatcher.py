"""Alert dispatcher.

When the switch warns, trips, or fires, the right people must be told
through the right channels, in the right order. This module is the glue
between the contact roster and the delivery channels: it decides WHO gets
told at each escalation level and HOW, then hands each message to a channel
and records the outcome.

The dispatcher is policy-driven. Each escalation level maps to a clearance
tier: a warning goes to alert-only contacts, a trip to full-clearance
contacts, a fire to everyone. For each contact it renders a message, picks
the contact's channel, and sends. Every send is logged so the event trail
shows exactly who was notified and whether it landed.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .channels import Channel, SendResult
from .contacts import Contact, Roster

__all__ = ["DispatchError", "Dispatcher", "LEVEL_CLEARANCE"]


class DispatchError(ValueError):
    """Raised for dispatcher misuse."""


#: Which clearance tier each escalation level notifies.
LEVEL_CLEARANCE = {
    "warn": "alert-only",
    "trip": "full",
    "fire": "none",  # everyone
}


class Dispatcher:
    """Routes escalation alerts to contacts through channels."""

    def __init__(self, roster: Roster,
                 channels: Optional[Dict[str, Channel]] = None) -> None:
        self._roster = roster
        self._channels = dict(channels or {})
        self._log: List[Dict] = []

    def register_channel(self, scheme: str, channel: Channel) -> None:
        """Bind a channel to a URI scheme like 'email' or 'sms'."""
        if not scheme.strip():
            raise DispatchError("scheme must not be empty")
        self._channels[scheme.strip().lower()] = channel

    def _channel_for(self, contact: Contact) -> Optional[Channel]:
        """Pick the channel matching the contact's channel URI scheme."""
        scheme = contact.channel.split(":", 1)[0].strip().lower()
        return self._channels.get(scheme)

    def render_message(self, level: str, contact: Contact,
                       switch_id: str) -> str:
        """Build the alert text for one contact at one level."""
        if level not in LEVEL_CLEARANCE:
            raise DispatchError(f"unknown level {level!r}")
        verbs = {"warn": "WARNING", "trip": "TRIPPED", "fire": "FIRED"}
        return (f"[dms:{switch_id}] {verbs[level]} — {contact.name}, the "
                f"dead man's switch has {verbs[level].lower()}. "
                "Follow the runbook.")

    def dispatch(self, level: str, switch_id: str) -> List[SendResult]:
        """Notify every contact cleared for this level.

        Returns the SendResult for each attempted contact. Contacts with no
        matching channel are recorded as failed sends, not skipped silently.
        """
        if level not in LEVEL_CLEARANCE:
            raise DispatchError(f"unknown level {level!r}")
        clearance = LEVEL_CLEARANCE[level]
        results: List[SendResult] = []
        for contact in self._roster.cleared(clearance):
            message = self.render_message(level, contact, switch_id)
            channel = self._channel_for(contact)
            if channel is None:
                result = SendResult(False, "none",
                                    f"no channel for {contact.channel!r}")
            else:
                result = channel.send(message)
            self._log.append({
                "level": level,
                "contact": contact.name,
                "ok": result.ok,
                "detail": result.detail,
            })
            results.append(result)
        return results

    @property
    def log(self) -> List[Dict]:
        """Every dispatch attempt, in order."""
        return list(self._log)

    def notified(self, level: Optional[str] = None) -> List[str]:
        """Names of contacts successfully notified, optionally by level."""
        return [entry["contact"] for entry in self._log
                if entry["ok"] and (level is None or entry["level"] == level)]
