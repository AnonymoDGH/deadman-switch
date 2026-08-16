"""Human-readable reports for the dead man's switch.

Operators and handlers need to see what a switch is doing at a glance: is
it alive, how much slack is left, what would fire, and -- after the fact --
the full timeline of how it reached its end state. This module renders
those views from the engine, the event log, and the simulator result.

Three reports are provided:

* status_report  -- a live snapshot: state, age, slack, next stage.
* timeline_report -- the event log as a readable, dated sequence.
* postmortem_report -- after a fire, the full story with the payload result.

All are pure string builders, so they are trivially testable and can be
written to a file or printed by the CLI.
"""

from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional

from .events import EventLog
from .state import State

__all__ = [
    "format_timestamp",
    "status_report",
    "timeline_report",
    "postmortem_report",
]


def format_timestamp(ts: float) -> str:
    """Render a Unix timestamp as a compact UTC string."""
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC")


def status_report(state: str, age: Optional[float],
                  slack: Optional[float], ttl_seconds: float,
                  grace_seconds: float = 0.0,
                  payload_type: str = "print") -> str:
    """A live snapshot of one switch."""
    lines = ["DEAD MAN'S SWITCH — STATUS", "=" * 40]
    lines.append(f"state:        {state}")
    if state == State.DISARMED:
        lines.append("The switch is disarmed. No heartbeat is required.")
        return "\n".join(lines)
    if state == State.FIRED:
        lines.append("The switch has FIRED. The payload was executed.")
        return "\n".join(lines)

    if age is not None:
        lines.append(f"last beat:    {age:.0f}s ago")
    lines.append(f"ttl:          {ttl_seconds:.0f}s")
    if grace_seconds > 0:
        lines.append(f"grace:        {grace_seconds:.0f}s")
    if slack is not None:
        lines.append(f"slack left:   {slack:.0f}s")
    lines.append(f"payload:      {payload_type}")

    if state == State.ARMED:
        lines.append("verdict:      ALIVE — keep beating.")
    elif state == State.WARNING:
        lines.append("verdict:      WARNING — beat now to reset.")
    elif state == State.TRIPPED:
        lines.append("verdict:      TRIPPED — beat or cancel before it fires.")
    return "\n".join(lines)


def timeline_report(log: EventLog) -> str:
    """Render the event log as a readable sequence."""
    lines = ["EVENT TIMELINE", "=" * 40]
    if len(log) == 0:
        lines.append("(no events recorded)")
        return "\n".join(lines)
    for event in log.events:
        when = format_timestamp(event.at) if event.at else "t=?"
        detail = ""
        if event.detail:
            pairs = ", ".join(f"{k}={v}" for k, v in
                              sorted(event.detail.items()))
            detail = f"  [{pairs}]"
        lines.append(f"#{event.seq:<3} {event.kind:<8} {when}{detail}")
    lines.append("-" * 40)
    lines.append(f"chain intact: {log.verify()}")
    return "\n".join(lines)


def postmortem_report(log: EventLog, final_state: str,
                      payload_result: Optional[Dict] = None) -> str:
    """The full story after a switch has run to completion."""
    lines = ["POST-MORTEM", "=" * 40]
    lines.append(f"final state:  {final_state}")

    kinds = log.kinds()
    lines.append(f"beats:        {kinds.get('beat', 0)}")
    lines.append(f"warnings:     {kinds.get('warn', 0)}")
    lines.append(f"trips:        {kinds.get('trip', 0)}")
    lines.append(f"rescues:      {kinds.get('rescue', 0)}")
    fired = kinds.get("fire", 0) > 0
    lines.append(f"fired:        {'yes' if fired else 'no'}")

    if fired:
        fire_events = [e for e in log.events if e.kind == "fire"]
        if fire_events:
            lines.append(f"fired at:     {format_timestamp(fire_events[0].at)}")
    if payload_result is not None:
        ok = payload_result.get("ok")
        lines.append(f"payload ok:   {'yes' if ok else 'NO'}")
        lines.append(f"payload note: {payload_result.get('detail', '')}")

    lines.append("")
    lines.append(timeline_report(log))
    return "\n".join(lines)
