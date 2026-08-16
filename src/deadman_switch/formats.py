"""Config and state serialization formats.

The switch stores its config as JSON, but humans sometimes need other
views: a compact one-line summary for a status board, an INI-style block
for pasting into a runbook, or a redacted version that can be shared with a
third party without leaking the payload or any secrets.

This module provides pure converters between the canonical config dict and
those formats. Every converter is deterministic and round-trips where it
makes sense, so the CLI and the tests can rely on stable output.
"""

from __future__ import annotations

import json
from typing import Dict, List

__all__ = [
    "FormatError",
    "to_json",
    "from_json",
    "to_ini",
    "to_oneline",
    "to_redacted",
    "REDACT_KEYS",
]


class FormatError(ValueError):
    """Raised for malformed input to a converter."""


def to_json(config: Dict, indent: int = 2) -> str:
    """Serialize a config dict to pretty JSON."""
    return json.dumps(config, indent=indent, sort_keys=True,
                      ensure_ascii=False)


def from_json(text: str) -> Dict:
    """Parse JSON back into a config dict.

    Raises:
        FormatError: If the text is not a JSON object.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FormatError(f"not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise FormatError("config JSON must be an object")
    return data


def to_ini(config: Dict) -> str:
    """Render a config as an INI-style block for runbooks.

    Nested dicts (like the payload) are flattened with dotted keys so the
    result stays two-dimensional and readable.
    """
    lines = ["[switch]"]

    def emit(prefix: str, value) -> None:
        if isinstance(value, dict):
            for key in sorted(value):
                emit(f"{prefix}{key}.", value[key])
        else:
            lines.append(f"{prefix.rstrip('.')} = {value}")

    for key in sorted(config):
        if key == "payload" and isinstance(config[key], dict):
            lines.append("")
            lines.append("[payload]")
            for pkey in sorted(config[key]):
                lines.append(f"{pkey} = {config[key][pkey]}")
            lines.append("")
            lines.append("[switch]")
        else:
            emit(f"{key}.", config[key])
    return "\n".join(lines)


def to_oneline(config: Dict) -> str:
    """A compact one-line summary for status boards."""
    payload = config.get("payload", {})
    return (f"ttl={config.get('ttl_seconds')}s "
            f"grace={config.get('grace_seconds', 0)}s "
            f"payload={payload.get('type', 'print')}")


#: Keys stripped from a redacted export.
REDACT_KEYS: List[str] = ["smtp_pass", "smtp_user", "passphrase", "secret",
                          "url", "command"]


def to_redacted(config: Dict) -> Dict:
    """A copy of the config safe to show a third party.

    Removes or masks sensitive keys (credentials, webhook URLs, commands)
    while keeping the shape and the non-sensitive settings. The original is
    not mutated.
    """
    def scrub(value):
        if isinstance(value, dict):
            return {k: ("[redacted]" if k in REDACT_KEYS else scrub(v))
                    for k, v in value.items()}
        if isinstance(value, list):
            return [scrub(v) for v in value]
        return value

    return scrub(config)
