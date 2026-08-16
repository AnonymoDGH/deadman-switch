"""Human-friendly time formatting and duration parsing.

Operators and handlers read "2h 30m", not "9000.0 seconds". This module
converts between machine seconds and the compact human forms used across
the CLI, the reports, and the runbook. It provides:

* format_duration  -- 9000 -> "2h 30m"
* parse_duration   -- "2h30m" -> 9000.0 (for --ttl style flags)
* relative_time    -- "3 minutes ago" / "in 2 hours"
* countdown        -- a one-line countdown string for a switch's slack

All functions are pure and deterministic. parse_duration accepts the
suffixes s/m/h/d (case-insensitive) and combinations like "1d2h3m4s", and
raises on anything ambiguous so a mistyped TTL never silently arms a
switch with the wrong fuse.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

__all__ = [
    "TimeFormatError",
    "format_duration",
    "parse_duration",
    "relative_time",
    "countdown",
]


class TimeFormatError(ValueError):
    """Raised for invalid time input."""


_UNIT_SECONDS = {
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
    "d": 86400.0,
}

_TOKEN = re.compile(r"(\d+(?:\.\d+)?)([smhd])", re.IGNORECASE)


def format_duration(seconds: float) -> str:
    """Render seconds as a compact human string.

    Uses the largest units that matter and drops trailing zero units:
    9000 -> "2h 30m", 45 -> "45s", 90061 -> "1d 1h 1m". Sub-second values
    render as "0s".
    """
    if seconds < 0:
        raise TimeFormatError("seconds must be >= 0")
    total = int(seconds)
    if total == 0:
        return "0s"
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")
    return " ".join(parts)


def parse_duration(text: str) -> float:
    """Parse a human duration like "2h30m" into seconds.

    Accepts s/m/h/d suffixes in any combination and case. A bare number
    (no suffix) is treated as seconds. Raises TimeFormatError on empty,
    negative, or unparseable input, and on repeated units like "1h1h".
    """
    if not text or not text.strip():
        raise TimeFormatError("duration must not be empty")
    text = text.strip().lower()

    # Bare number -> seconds.
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)

    seen = set()
    total = 0.0
    pos = 0
    for match in _TOKEN.finditer(text):
        if match.start() != pos:
            raise TimeFormatError(
                f"unexpected characters in duration {text!r}")
        value, unit = match.groups()
        if unit in seen:
            raise TimeFormatError(f"repeated unit {unit!r} in {text!r}")
        seen.add(unit)
        total += float(value) * _UNIT_SECONDS[unit]
        pos = match.end()
    if pos != len(text):
        raise TimeFormatError(f"trailing characters in duration {text!r}")
    if total <= 0:
        raise TimeFormatError("duration must be positive")
    return total


def relative_time(delta_seconds: float) -> str:
    """Render an offset from now as "X ago" or "in X".

    Positive delta means the moment is in the past; negative means the
    future.
    """
    magnitude = format_duration(abs(delta_seconds))
    if delta_seconds >= 0:
        return f"{magnitude} ago"
    return f"in {magnitude}"


def countdown(slack_seconds: Optional[float], state: str) -> str:
    """A one-line countdown string for a switch's remaining slack.

    For live states with slack, shows the time left before the next
    escalation. For terminal or unknown states, says so plainly.
    """
    if state in ("fired",):
        return "FIRED — payload already executed."
    if state in ("disarmed",):
        return "disarmed — no countdown."
    if slack_seconds is None:
        return "no heartbeat recorded — countdown unknown."
    if slack_seconds <= 0:
        return "slack exhausted — escalation imminent."
    return f"{format_duration(slack_seconds)} of slack left."
