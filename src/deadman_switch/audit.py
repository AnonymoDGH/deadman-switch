"""Configuration auditing and security linting.

A dead man's switch is only as good as its configuration. A TTL that is too
short fires on a long flight; a payload with no error handling may fail
silently; a heartbeat file in a world-writable directory can be kept alive by
anyone. This module audits a config dict and reports findings, each with a
severity and a human-readable message.

Findings are advisory, not fatal: the audit never raises on a bad config, it
reports. That lets the CLI show a health report and lets tests assert on
specific misconfigurations. Severity levels are "info", "warn", and
"critical"; a config with any critical finding should not be armed.
"""

from __future__ import annotations

from typing import Dict, List

__all__ = [
    "SEVERITIES",
    "Finding",
    "audit_config",
    "audit_payload",
    "is_armable",
]

SEVERITIES = ("info", "warn", "critical")

#: TTLs shorter than this are almost always a mistake.
MIN_SAFE_TTL = 300
#: TTLs longer than this may indicate a forgotten switch.
MAX_REASONABLE_TTL = 365 * 24 * 3600


class Finding:
    """One audit finding."""

    def __init__(self, severity: str, code: str, message: str) -> None:
        if severity not in SEVERITIES:
            raise ValueError(f"unknown severity {severity!r}")
        self.severity = severity
        self.code = code
        self.message = message

    def __repr__(self) -> str:
        return f"Finding({self.severity}, {self.code!r}, {self.message!r})"

    def __eq__(self, other) -> bool:
        return (isinstance(other, Finding)
                and (self.severity, self.code, self.message)
                == (other.severity, other.code, other.message))


def audit_payload(payload: Dict) -> List[Finding]:
    """Audit just the payload section of a config."""
    findings: List[Finding] = []
    ptype = payload.get("type")
    if ptype is None:
        findings.append(Finding("critical", "payload-missing-type",
                                "payload has no 'type' field"))
        return findings
    if ptype == "print":
        if not payload.get("message"):
            findings.append(Finding("warn", "payload-empty-message",
                                    "print payload has an empty message"))
    elif ptype == "webhook":
        url = payload.get("url", "")
        if not url:
            findings.append(Finding("critical", "webhook-no-url",
                                    "webhook payload has no url"))
        elif url.startswith("http://"):
            findings.append(Finding("warn", "webhook-insecure",
                                    "webhook url uses plain http"))
    elif ptype == "email":
        for field in ("to", "subject"):
            if not payload.get(field):
                findings.append(Finding("critical", f"email-no-{field}",
                                        f"email payload missing {field}"))
        if payload.get("smtp_pass") and not payload.get("smtp_user"):
            findings.append(Finding("warn", "email-pass-without-user",
                                    "smtp_pass set but smtp_user missing"))
    elif ptype == "command":
        command = payload.get("command", "")
        if not command:
            findings.append(Finding("critical", "command-empty",
                                    "command payload is empty"))
        elif "rm -rf" in command:
            findings.append(Finding("critical", "command-destructive",
                                    "command contains 'rm -rf'"))
    elif ptype == "file":
        if not payload.get("path"):
            findings.append(Finding("critical", "file-no-path",
                                    "file payload has no path"))
    elif ptype == "notify":
        if not payload.get("label"):
            findings.append(Finding("warn", "notify-no-label",
                                    "notify payload has no label"))
    else:
        findings.append(Finding("critical", "payload-unknown-type",
                                f"unknown payload type {ptype!r}"))
    return findings


def audit_config(config: Dict) -> List[Finding]:
    """Audit a full switch config dict. Never raises."""
    findings: List[Finding] = []

    ttl = config.get("ttl_seconds")
    if ttl is None:
        findings.append(Finding("critical", "ttl-missing",
                                "config has no ttl_seconds"))
    elif not isinstance(ttl, (int, float)) or ttl <= 0:
        findings.append(Finding("critical", "ttl-invalid",
                                "ttl_seconds must be a positive number"))
    else:
        if ttl < MIN_SAFE_TTL:
            findings.append(Finding("warn", "ttl-too-short",
                                    f"ttl {ttl}s is very short; a brief "
                                    "outage could fire the switch"))
        if ttl > MAX_REASONABLE_TTL:
            findings.append(Finding("info", "ttl-very-long",
                                    f"ttl {ttl}s exceeds a year; the switch "
                                    "may be forgotten"))

    grace = config.get("grace_seconds", 0)
    if grace and ttl and isinstance(ttl, (int, float)):
        if grace >= ttl:
            findings.append(Finding("warn", "grace-exceeds-ttl",
                                    "grace_seconds >= ttl_seconds; the "
                                    "warning phase dominates"))

    hb = config.get("heartbeat")
    if hb is None:
        findings.append(Finding("info", "heartbeat-default",
                                "using the default heartbeat path"))
    elif isinstance(hb, str):
        lowered = hb.lower()
        if "temp" in lowered or lowered.startswith("/tmp"):
            findings.append(Finding("warn", "heartbeat-temp-dir",
                                    "heartbeat file lives in a temp "
                                    "directory; it may be cleaned up"))

    payload = config.get("payload")
    if payload is None:
        findings.append(Finding("critical", "payload-missing",
                                "config has no payload"))
    elif isinstance(payload, dict):
        findings.extend(audit_payload(payload))
    else:
        findings.append(Finding("critical", "payload-not-dict",
                                "payload must be a dict"))

    return findings


def is_armable(config: Dict) -> bool:
    """True if the config has no critical findings."""
    return not any(f.severity == "critical" for f in audit_config(config))
