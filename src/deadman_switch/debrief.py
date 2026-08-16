"""Post-incident debrief generator.

After a switch incident -- a fire, a false alarm, a rescue -- the team
needs a structured debrief: what happened, in what order, what worked, what
didn't, and what to change. Writing that from memory is unreliable; the
event log already knows the truth. This module assembles a debrief report
from the event log, the journal, and the outcome, and leaves structured
blanks for the human analysis.

The debrief is deterministic for a given set of inputs, so it can be
regenerated as more information lands. It renders as markdown suitable for
a wiki page or an after-action file.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .events import EventLog
from .journal import Journal

__all__ = ["DebriefError", "classify_outcome", "render_debrief"]


class DebriefError(ValueError):
    """Raised for debrief misuse."""


def classify_outcome(log: EventLog) -> Dict:
    """Derive the factual outcome from the event log.

    Returns a dict with fired (bool), rescued (bool), beats, warnings,
    trips, and cancels counts.
    """
    kinds = log.kinds()
    fired = kinds.get("fire", 0) > 0
    rescued = kinds.get("rescue", 0) > 0
    return {
        "fired": fired,
        "rescued": rescued,
        "beats": kinds.get("beat", 0),
        "warnings": kinds.get("warn", 0),
        "trips": kinds.get("trip", 0),
        "cancels": kinds.get("cancel", 0),
    }


def render_debrief(log: EventLog,
                   journal: Optional[Journal] = None,
                   switch_id: str = "switch",
                   summary: str = "") -> str:
    """Assemble the after-action debrief as markdown.

    The factual sections (timeline, outcome, journal) are filled from the
    data; the analysis sections are left as prompts for the humans.
    """
    if len(log) == 0:
        raise DebriefError("cannot debrief an empty event log")

    outcome = classify_outcome(log)
    lines: List[str] = []
    lines.append(f"# Debrief: {switch_id}")
    lines.append("")
    if summary:
        lines.append(summary)
        lines.append("")

    lines.append("## Outcome (from the event log)")
    lines.append("")
    lines.append(f"- Fired: **{'yes' if outcome['fired'] else 'no'}**")
    lines.append(f"- Rescued from escalation: "
                 f"{'yes' if outcome['rescued'] else 'no'}")
    lines.append(f"- Beats: {outcome['beats']}")
    lines.append(f"- Warnings: {outcome['warnings']}")
    lines.append(f"- Trips: {outcome['trips']}")
    lines.append(f"- Cancels: {outcome['cancels']}")
    lines.append(f"- Event chain intact: {log.verify()}")
    lines.append("")

    lines.append("## Timeline")
    lines.append("")
    for event in log.events:
        detail = ""
        if event.detail:
            pairs = ", ".join(f"{k}={v}" for k, v in
                              sorted(event.detail.items()))
            detail = f" ({pairs})"
        lines.append(f"- `#{event.seq}` **{event.kind}**{detail}")
    lines.append("")

    if journal is not None and len(journal) > 0:
        lines.append("## Operator journal")
        lines.append("")
        for entry in journal.entries:
            tags = f" [{', '.join(entry.tags)}]" if entry.tags else ""
            lines.append(f"- t={entry.ts:.0f}: {entry.text}{tags}")
        lines.append("")

    lines.append("## Analysis (fill in)")
    lines.append("")
    lines.append("- What was the root cause of the escalation?")
    lines.append("- Did the TTL/grace sizing behave as expected?")
    lines.append("- Were the right contacts notified in time?")
    lines.append("- What would we change before re-arming?")
    lines.append("")
    return "\n".join(lines)
