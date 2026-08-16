"""Tests for deadman_switch.formats -- config serialization formats."""

from __future__ import annotations

import pytest

from deadman_switch.formats import (
    FormatError, from_json, to_ini, to_json, to_oneline, to_redacted,
)


def _config():
    return {
        "ttl_seconds": 3600,
        "grace_seconds": 600,
        "heartbeat": "/tmp/hb",
        "payload": {"type": "email", "to": "a@b.c",
                    "smtp_user": "user", "smtp_pass": "secret"},
    }


def test_json_roundtrip():
    config = _config()
    assert from_json(to_json(config)) == config


def test_from_json_invalid():
    with pytest.raises(FormatError):
        from_json("{not json")


def test_from_json_non_object():
    with pytest.raises(FormatError):
        from_json("[1, 2, 3]")


def test_to_ini_has_sections():
    text = to_ini(_config())
    assert "[switch]" in text
    assert "[payload]" in text
    assert "ttl_seconds = 3600" in text
    assert "type = email" in text


def test_to_ini_deterministic():
    assert to_ini(_config()) == to_ini(_config())


def test_to_oneline():
    text = to_oneline(_config())
    assert "ttl=3600s" in text
    assert "grace=600s" in text
    assert "payload=email" in text


def test_to_oneline_defaults():
    text = to_oneline({})
    assert "payload=print" in text


def test_to_redacted_masks_secrets():
    red = to_redacted(_config())
    assert red["payload"]["smtp_pass"] == "[redacted]"
    assert red["payload"]["smtp_user"] == "[redacted]"
    # Non-sensitive values survive.
    assert red["payload"]["to"] == "a@b.c"
    assert red["ttl_seconds"] == 3600


def test_to_redacted_does_not_mutate():
    config = _config()
    before = config["payload"]["smtp_pass"]
    to_redacted(config)
    assert config["payload"]["smtp_pass"] == before


def test_to_redacted_nested_lists():
    config = {"items": [{"secret": "x"}, {"ok": "y"}]}
    red = to_redacted(config)
    assert red["items"][0]["secret"] == "[redacted]"
    assert red["items"][1]["ok"] == "y"
