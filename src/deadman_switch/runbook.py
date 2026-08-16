"""Runbook generation for switch handlers.

When a switch trips, the handler should not be improvising. This module
renders a complete operating runbook as markdown: how to arm, how to beat,
what each state means, what to do when the switch warns or trips, how to
cancel safely, and who to contact. The runbook is generated from the actual
config, so the TTLs, payload type, and contact list in it match the switch
it documents.

The output is deterministic for a given config, so it can be regenerated
after every config change and diffed. It is deliberately plain markdown with
no external assets, so it can be printed, pasted into a wiki, or read on a
phone.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .schedule import cron_hint, plan_beats

__all__ = ["render_runbook", "state_table", "emergency_section"]


def state_table() -> str:
    """A markdown table explaining every switch state."""
    rows = [
        ("DISARMED", "Off. No heartbeat required.", "arm"),
        ("ARMED", "Live and healthy. Keep beating.", "beat"),
        ("WARNING", "TTL exceeded, grace running. Beat NOW.", "beat"),
        ("TRIPPED", "Grace exhausted. Fire imminent.", "beat / cancel"),
        ("FIRED", "Payload executed. Too late.", "post-mortem"),
    ]
    lines = ["| State | Meaning | Action |", "|---|---|---|"]
    for state, meaning, action in rows:
        lines.append(f"| {state} | {meaning} | {action} |")
    return "\n".join(lines)


def emergency_section(contacts: List[Dict]) -> str:
    """The who-to-call section, built from the contact roster."""
    lines = ["## Emergency contacts", ""]
    if not contacts:
        lines.append("_No contacts configured. Add some before arming._")
        return "\n".join(lines)
    for contact in contacts:
        lines.append(f"- **{contact['name']}** via `{contact['channel']}` "
                     f"(clearance: {contact.get('clearance', 'alert-only')})")
    return "\n".join(lines)


def render_runbook(config: Dict,
                   contacts: Optional[List[Dict]] = None,
                   operator: str = "the operator") -> str:
    """Render the full runbook for one switch config."""
    ttl = config.get("ttl_seconds", 0)
    grace = config.get("grace_seconds", 0)
    payload = config.get("payload", {})
    ptype = payload.get("type", "print")

    lines: List[str] = []
    lines.append("# Dead Man's Switch — Handler Runbook")
    lines.append("")
    lines.append(f"Operator: {operator}")
    lines.append("")

    lines.append("## Parameters")
    lines.append("")
    lines.append(f"- TTL: **{ttl}s** ({ttl / 3600:.1f}h) of silence before warning")
    if grace:
        lines.append(f"- Grace: **{grace}s** ({grace / 3600:.1f}h) between "
                     "warning and fire")
    else:
        lines.append("- Grace: none (fires immediately after TTL)")
    lines.append(f"- Payload: **{ptype}**")
    lines.append("")

    lines.append("## Beat schedule")
    lines.append("")
    if ttl:
        plan = plan_beats(ttl_seconds=ttl, window_seconds=ttl * 4, safety=0.5)
        lines.append(f"Beat every **{plan.interval:.0f}s** to keep a full "
                     "margin. One missed beat is survivable; two in a row is "
                     "not.")
        lines.append("")
        lines.append(f"Suggested cron: `{cron_hint(plan.interval)}`")
    lines.append("")

    lines.append("## States")
    lines.append("")
    lines.append(state_table())
    lines.append("")

    lines.append("## If the switch WARNS")
    lines.append("")
    lines.append("1. Beat immediately (`dms heartbeat`).")
    lines.append("2. Check why the beat was missed (device, network, travel).")
    lines.append("3. If travel is planned, extend the TTL BEFORE leaving.")
    lines.append("")

    lines.append("## If the switch TRIPS")
    lines.append("")
    lines.append("1. Beat to rescue if you are the operator.")
    lines.append("2. Otherwise verify the operator's status via the "
                 "proof-of-life channel.")
    lines.append("3. Cancel ONLY with the signed cancel token and, if "
                 "configured, quorum approval.")
    lines.append("4. Never cancel on an unverified voice request — use the "
                 "duress code check.")
    lines.append("")

    lines.append("## After a fire")
    lines.append("")
    lines.append("1. Run `dms report` and save the post-mortem.")
    lines.append("2. Verify the event log chain is intact (tamper check).")
    lines.append("3. Execute the follow-up plan for the payload type "
                 f"({ptype}).")
    lines.append("")

    lines.append(emergency_section(contacts or []))
    lines.append("")
    return "\n".join(lines)
