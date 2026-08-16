"""Persistent storage for switch state.

The engine keeps everything in memory, which is fine for a single run but a
real switch must survive restarts: the armed state, the last beat, the
event log, and the escalation policy all need to be on disk. This module
provides a simple file-backed store that serializes one switch's full state
to a directory and restores it.

Layout of a store directory:

    <dir>/
      switch.json     -- config + state + last beat + policy
      events.jsonl    -- the hash-chained event log

Saving is atomic (write to a temp file, then rename) so a crash mid-write
cannot corrupt the store. Loading verifies the event-log chain and reports
tampering instead of silently trusting the file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional

from .events import EventLog

__all__ = ["StoreError", "SwitchStore"]

_SWITCH_FILE = "switch.json"
_EVENTS_FILE = "events.jsonl"


class StoreError(RuntimeError):
    """Raised when the store is missing, corrupt, or tampered."""


class SwitchStore:
    """File-backed persistence for one switch."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    # -- paths --------------------------------------------------------------

    @property
    def switch_path(self) -> Path:
        return self.directory / _SWITCH_FILE

    @property
    def events_path(self) -> Path:
        return self.directory / _EVENTS_FILE

    def exists(self) -> bool:
        return self.switch_path.exists()

    # -- save ---------------------------------------------------------------

    def save(self, state: Dict, log: EventLog) -> None:
        """Atomically persist the switch state and event log."""
        self.directory.mkdir(parents=True, exist_ok=True)
        self._atomic_write(self.switch_path,
                           json.dumps(state, indent=2, sort_keys=True) + "\n")
        self._atomic_write(self.events_path, log.to_text() + "\n")

    def _atomic_write(self, path: Path, text: str) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)

    # -- load ---------------------------------------------------------------

    def load(self, verify_chain: bool = True) -> Dict:
        """Load the switch state and event log.

        Returns a dict with keys 'state' and 'log'. If verify_chain is true
        and the event log fails verification, raises StoreError.

        Raises:
            StoreError: If the store is missing, corrupt, or tampered.
        """
        if not self.exists():
            raise StoreError(f"no store at {self.directory}")
        try:
            state = json.loads(self.switch_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreError(f"corrupt switch file: {exc}") from exc

        log = EventLog()
        if self.events_path.exists():
            try:
                log = EventLog.from_text(
                    self.events_path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise StoreError(f"corrupt event log: {exc}") from exc
            if verify_chain and not log.verify():
                broken = log.first_broken()
                raise StoreError(
                    f"event log tampered (first broken at seq {broken})")
        return {"state": state, "log": log}

    def load_state_only(self) -> Dict:
        """Load just the switch state dict, ignoring the event log."""
        if not self.exists():
            raise StoreError(f"no store at {self.directory}")
        try:
            return json.loads(self.switch_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreError(f"corrupt switch file: {exc}") from exc

    def clear(self) -> None:
        """Remove the store files (not the directory)."""
        for path in (self.switch_path, self.events_path):
            if path.exists():
                path.unlink()
