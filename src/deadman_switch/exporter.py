"""Export switch state and history in portable formats.

A handler needs to move switch evidence around: into a report, into an
archive, or to another handler taking over. This module renders the switch
state, its event log, and its journal into three formats:

* json      -- the full machine-readable dump.
* markdown  -- a human-readable briefing.
* cheat-sheet -- a one-screen summary for the wall or the wallet.

All exporters are pure functions over the data, so they are deterministic
and trivially testable. A redaction flag strips sensitive fields from any
format before it leaves the building.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from .events import EventLog
from .formats import to_redacted
from .journal import Journal

__all__ = [
    "ExportError",
    "export_json",
    "export_markdown",
    "export_cheat_sheet",
]


class ExportError(ValueError):
    """Raised for export misuse."""


def export_json(state: str, config: Dict, log: EventLog,
                journal: Optional[Journal] = None,
                redact: bool = False) -> str:
    """The full machine-readable dump of one switch."""
    payload: Dict = {
        "state": state,
        "config": config,
        "events": [e.to_dict() for e in log.events],
        "chain_intact": log.verify(),
    }
    if journal is not None:
        payload["journal"] = [e.to_dict() for e in journal.entries]
    if redact:
        payload = to_redacted(payload)
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def export_markdown(state: str, config: Dict, log: EventLog,
                    journal: Optional[Journal] = None,
                    switch_id: str = "switch") -> str:
    """A human-readable briefing in markdown."""
    ttl = config.get("ttl_seconds", 0)
    grace = config.get("grace_seconds", 0)
    payload = config.get("payload", {})

    lines: List[str] = []
    lines.append(f"# Switch briefing: {switch_id}")
    lines.append("")
    lines.append(f"- **State:** {state}")
    lines.append(f"- **TTL:** {ttl}s")
    if grace:
        lines.append(f"- **Grace:** {grace}s")
    lines.append(f"- **Payload:** {payload.get('type', 'print')}")
    lines.append(f"- **Event chain intact:** {log.verify()}")
    lines.append("")

    lines.append("## Events")
    lines.append("")
    if len(log) == 0:
        lines.append("_No events recorded._")
    else:
        for event in log.events:
            detail = ""
            if event.detail:
                pairs = ", ".join(f"{k}={v}" for k, v in
                                  sorted(event.detail.items()))
                detail = f" ({pairs})"
            lines.append(f"- `#{event.seq}` **{event.kind}**{detail}")
    lines.append("")

    if journal is not None and len(journal) > 0:
        lines.append("## Journal")
        lines.append("")
        for entry in journal.entries:
            tags = f" [{', '.join(entry.tags)}]" if entry.tags else ""
            lines.append(f"- t={entry.ts:.0f}: {entry.text}{tags}")
        lines.append("")
    return "\n".join(lines)


def export_cheat_sheet(state: str, config: Dict,
                       switch_id: str = "switch") -> str:
    """A one-screen summary for the wall or the wallet."""
    ttl = config.get("ttl_seconds", 0)
    grace = config.get("grace_seconds", 0)
    payload = config.get("payload", {})
    lines = [
        f"SWITCH {switch_id} — {state}",
        f"ttl {ttl}s | grace {grace}s | payload {payload.get('type', 'print')}",
        "beat: dms heartbeat",
        "status: dms status",
        "rescue: beat within grace",
        "cancel: signed token only",
    ]
    return "\n".join(lines)
