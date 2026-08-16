"""Validated, dry-runnable payload actions for the dead man's switch.

The original fire() executes a payload dict directly, which is fine for a
prop but risky in practice: a typo in the payload means the switch fires
and does nothing, or worse, does the wrong thing. This module wraps each
payload type in a validated action object that:

* checks its own configuration at construction time (fail early, not at fire),
* supports a dry_run that reports what it WOULD do without doing it,
* returns a structured result so the event log can record success/failure.

Supported actions: print, webhook, email, command, file (write a message to
a path), and notify (a no-op hook for tests). Each is a subclass of
PayloadAction with validate(), dry_run(), and execute().
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

__all__ = [
    "PayloadError",
    "PayloadResult",
    "PayloadAction",
    "PrintAction",
    "FileAction",
    "WebhookAction",
    "EmailAction",
    "CommandAction",
    "NotifyAction",
    "build_action",
    "ACTION_TYPES",
]


class PayloadError(ValueError):
    """Raised when a payload action is misconfigured."""


class PayloadResult:
    """The outcome of executing (or dry-running) a payload action."""

    def __init__(self, action: str, ok: bool, detail: str,
                 dry_run: bool = False) -> None:
        self.action = action
        self.ok = ok
        self.detail = detail
        self.dry_run = dry_run

    def to_dict(self) -> Dict:
        return {"action": self.action, "ok": self.ok,
                "detail": self.detail, "dry_run": self.dry_run}

    def __repr__(self) -> str:
        mode = " (dry-run)" if self.dry_run else ""
        return f"PayloadResult({self.action}, ok={self.ok}{mode})"


class PayloadAction:
    """Base class for all payload actions."""

    #: Subclasses set this to their type name.
    type_name = "base"

    def __init__(self, config: Dict) -> None:
        self.config = dict(config)
        self.validate()

    def validate(self) -> None:
        """Check the config; raise PayloadError on problems."""
        raise NotImplementedError

    def dry_run(self) -> PayloadResult:
        """Report what execute() would do, without doing it."""
        raise NotImplementedError

    def execute(self) -> PayloadResult:
        """Perform the action and return a result."""
        raise NotImplementedError

    def _require(self, key: str) -> str:
        value = self.config.get(key)
        if not value:
            raise PayloadError(
                f"{self.type_name} payload requires {key!r}")
        return str(value)


class PrintAction(PayloadAction):
    """Print a message to stdout."""

    type_name = "print"

    def validate(self) -> None:
        self._message = self.config.get("message", "Dead man's switch fired.")

    def dry_run(self) -> PayloadResult:
        return PayloadResult(self.type_name, True,
                             f"would print: {self._message!r}", dry_run=True)

    def execute(self) -> PayloadResult:
        print(self._message)
        return PayloadResult(self.type_name, True, f"printed: {self._message!r}")


class FileAction(PayloadAction):
    """Write a message to a file path."""

    type_name = "file"

    def validate(self) -> None:
        self._path = Path(self._require("path"))
        self._message = self.config.get("message", "Dead man's switch fired.")

    def dry_run(self) -> PayloadResult:
        return PayloadResult(self.type_name, True,
                             f"would write to {self._path}", dry_run=True)

    def execute(self) -> PayloadResult:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(self._message + "\n", encoding="utf-8")
            return PayloadResult(self.type_name, True, f"wrote {self._path}")
        except OSError as exc:
            return PayloadResult(self.type_name, False, f"write failed: {exc}")


class WebhookAction(PayloadAction):
    """POST JSON to a URL. (Requires network; dry_run is safe offline.)"""

    type_name = "webhook"

    def validate(self) -> None:
        self._url = self._require("url")
        if not self._url.startswith(("http://", "https://")):
            raise PayloadError("webhook url must start with http(s)://")

    def dry_run(self) -> PayloadResult:
        return PayloadResult(self.type_name, True,
                             f"would POST to {self._url}", dry_run=True)

    def execute(self) -> PayloadResult:
        import urllib.request
        data = self.config.get("data", "{}")
        if isinstance(data, dict):
            data = json.dumps(data)
        try:
            req = urllib.request.Request(
                self._url, data=data.encode(),
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
            return PayloadResult(self.type_name, True, f"posted to {self._url}")
        except Exception as exc:  # network errors are not fatal to the log
            return PayloadResult(self.type_name, False, f"post failed: {exc}")


class EmailAction(PayloadAction):
    """Send an email via SMTP. (Requires a server; dry_run is safe.)"""

    type_name = "email"

    def validate(self) -> None:
        self._to = self._require("to")
        self._from = self._require("from")
        self._host = self._require("smtp_host")

    def dry_run(self) -> PayloadResult:
        return PayloadResult(self.type_name, True,
                             f"would email {self._to} via {self._host}",
                             dry_run=True)

    def execute(self) -> PayloadResult:
        import smtplib
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["From"] = self._from
        msg["To"] = self._to
        msg["Subject"] = self.config.get("subject", "Dead Man's Switch")
        msg.set_content(self.config.get("message", "The switch has fired."))
        try:
            with smtplib.SMTP(self._host,
                              self.config.get("smtp_port", 587)) as s:
                s.starttls()
                if self.config.get("smtp_user"):
                    s.login(self.config["smtp_user"],
                            self.config.get("smtp_pass", ""))
                s.send_message(msg)
            return PayloadResult(self.type_name, True, f"emailed {self._to}")
        except Exception as exc:
            return PayloadResult(self.type_name, False, f"email failed: {exc}")


class CommandAction(PayloadAction):
    """Run a shell command."""

    type_name = "command"

    def validate(self) -> None:
        self._command = self._require("command")

    def dry_run(self) -> PayloadResult:
        return PayloadResult(self.type_name, True,
                             f"would run: {self._command!r}", dry_run=True)

    def execute(self) -> PayloadResult:
        proc = subprocess.run(self._command, shell=True, check=False,
                              capture_output=True, text=True)
        ok = proc.returncode == 0
        detail = f"exit {proc.returncode}"
        if not ok and proc.stderr:
            detail += f": {proc.stderr.strip()[:120]}"
        return PayloadResult(self.type_name, ok, detail)


class NotifyAction(PayloadAction):
    """A no-op hook for tests and integrations; records that it ran."""

    type_name = "notify"

    #: Class-level sink so tests can observe notifications.
    sink: List[Dict] = []

    def validate(self) -> None:
        self._label = self.config.get("label", "notify")

    def dry_run(self) -> PayloadResult:
        return PayloadResult(self.type_name, True,
                             f"would notify {self._label!r}", dry_run=True)

    def execute(self) -> PayloadResult:
        NotifyAction.sink.append({"label": self._label,
                                  "config": self.config})
        return PayloadResult(self.type_name, True, f"notified {self._label!r}")


#: Registry of type name -> action class.
ACTION_TYPES: Dict[str, type] = {
    "print": PrintAction,
    "file": FileAction,
    "webhook": WebhookAction,
    "email": EmailAction,
    "command": CommandAction,
    "notify": NotifyAction,
}


def build_action(config: Dict) -> PayloadAction:
    """Build the right action object for a payload config dict.

    Raises:
        PayloadError: If the type is unknown or the config is invalid.
    """
    kind = config.get("type", "print")
    if kind not in ACTION_TYPES:
        raise PayloadError(f"unknown payload type {kind!r}")
    return ACTION_TYPES[kind](config)
