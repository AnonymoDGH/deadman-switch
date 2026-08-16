"""Operator journal.

Heartbeats prove liveness, but they carry no context. A handler reviewing
after the fact wants to know not just THAT the operator beat, but what was
happening: "boarding flight, next beat in 9h", "safe at hotel". This module
keeps a journal of dated, tagged entries that ride alongside the switch.

Entries are append-only and can be filtered by tag or time window, so a
handler can reconstruct the operator's last known movements from the
journal alone. The journal is pure in-memory data with text serialization,
so it can be persisted by the store or exported by the CLI.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

__all__ = ["JournalError", "Entry", "Journal"]


class JournalError(ValueError):
    """Raised for journal misuse."""


class Entry:
    """One dated, tagged journal entry."""

    def __init__(self, ts: float, text: str,
                 tags: Optional[List[str]] = None) -> None:
        if not text.strip():
            raise JournalError("entry text must not be empty")
        self.ts = ts
        self.text = text.strip()
        self.tags = [t.strip().lower() for t in (tags or []) if t.strip()]

    def to_dict(self) -> Dict:
        return {"ts": self.ts, "text": self.text, "tags": self.tags}

    @classmethod
    def from_dict(cls, data: Dict) -> "Entry":
        try:
            return cls(ts=data["ts"], text=data["text"],
                       tags=data.get("tags"))
        except KeyError as exc:
            raise JournalError(f"entry missing field {exc}") from exc

    def __repr__(self) -> str:
        return f"Entry(ts={self.ts}, text={self.text!r}, tags={self.tags})"


class Journal:
    """An append-only, time-ordered journal."""

    def __init__(self) -> None:
        self._entries: List[Entry] = []

    def add(self, ts: float, text: str,
            tags: Optional[List[str]] = None) -> Entry:
        """Append one entry. Timestamps must not go backwards."""
        if self._entries and ts < self._entries[-1].ts:
            raise JournalError("entries must be added in time order")
        entry = Entry(ts, text, tags)
        self._entries.append(entry)
        return entry

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> List[Entry]:
        return list(self._entries)

    def by_tag(self, tag: str) -> List[Entry]:
        """All entries carrying one tag."""
        wanted = tag.strip().lower()
        return [e for e in self._entries if wanted in e.tags]

    def window(self, start: float, end: float) -> List[Entry]:
        """Entries with start <= ts <= end."""
        if end < start:
            raise JournalError("window end must be >= start")
        return [e for e in self._entries if start <= e.ts <= end]

    def last(self, n: int = 1) -> List[Entry]:
        """The most recent n entries, oldest first."""
        if n < 1:
            raise JournalError("n must be >= 1")
        return self._entries[-n:]

    def all_tags(self) -> List[str]:
        """Every distinct tag used, sorted."""
        seen = set()
        for entry in self._entries:
            seen.update(entry.tags)
        return sorted(seen)

    def to_text(self) -> str:
        """Serialize to a portable JSON-lines format."""
        return "\n".join(json.dumps(e.to_dict(), sort_keys=True)
                         for e in self._entries)

    @classmethod
    def from_text(cls, text: str) -> "Journal":
        """Parse to_text() output back into a Journal."""
        journal = cls()
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise JournalError(f"corrupt journal line: {exc}") from exc
            entry = Entry.from_dict(data)
            if journal._entries and entry.ts < journal._entries[-1].ts:
                raise JournalError("journal entries out of order")
            journal._entries.append(entry)
        return journal
