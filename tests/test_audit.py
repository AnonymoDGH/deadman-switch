"""Tests for deadman_switch.audit -- configuration auditing."""

from __future__ import annotations

import pytest

from deadman_switch.audit import (
    Finding, audit_config, audit_payload, is_armable,
)


def _good_config():
    return {
        "ttl_seconds": 3600,
        "heartbeat": "/home/op/.dms/heartbeat",
        "payload": {"type": "print", "message": "fired"},
    }


def _codes(findings):
    return {f.code for f in findings}


def test_good_config_clean():
    assert audit_config(_good_config()) == []
    assert is_armable(_good_config()) is True


def test_missing_ttl():
    cfg = _good_config()
    del cfg["ttl_seconds"]
    assert "ttl-missing" in _codes(audit_config(cfg))
    assert is_armable(cfg) is False


def test_invalid_ttl():
    cfg = _good_config()
    cfg["ttl_seconds"] = -5
    assert "ttl-invalid" in _codes(audit_config(cfg))


def test_short_ttl_warns():
    cfg = _good_config()
    cfg["ttl_seconds"] = 60
    assert "ttl-too-short" in _codes(audit_config(cfg))
    assert is_armable(cfg) is True  # warn, not critical


def test_very_long_ttl_info():
    cfg = _good_config()
    cfg["ttl_seconds"] = 2 * 365 * 24 * 3600
    assert "ttl-very-long" in _codes(audit_config(cfg))


def test_grace_exceeds_ttl():
    cfg = _good_config()
    cfg["grace_seconds"] = 7200
    assert "grace-exceeds-ttl" in _codes(audit_config(cfg))


def test_heartbeat_temp_dir():
    cfg = _good_config()
    cfg["heartbeat"] = "/tmp/hb"
    assert "heartbeat-temp-dir" in _codes(audit_config(cfg))


def test_missing_payload():
    cfg = _good_config()
    del cfg["payload"]
    assert "payload-missing" in _codes(audit_config(cfg))
    assert is_armable(cfg) is False


def test_payload_not_dict():
    cfg = _good_config()
    cfg["payload"] = "oops"
    assert "payload-not-dict" in _codes(audit_config(cfg))


def test_webhook_no_url():
    findings = audit_payload({"type": "webhook"})
    assert "webhook-no-url" in _codes(findings)


def test_webhook_insecure():
    findings = audit_payload({"type": "webhook", "url": "http://x"})
    assert "webhook-insecure" in _codes(findings)


def test_email_missing_fields():
    findings = audit_payload({"type": "email"})
    codes = _codes(findings)
    assert "email-no-to" in codes
    assert "email-no-subject" in codes


def test_command_destructive():
    findings = audit_payload({"type": "command", "command": "rm -rf /"})
    assert "command-destructive" in _codes(findings)


def test_command_empty():
    findings = audit_payload({"type": "command", "command": ""})
    assert "command-empty" in _codes(findings)


def test_file_no_path():
    findings = audit_payload({"type": "file"})
    assert "file-no-path" in _codes(findings)


def test_unknown_payload_type():
    findings = audit_payload({"type": "bogus"})
    assert "payload-unknown-type" in _codes(findings)


def test_finding_bad_severity():
    with pytest.raises(ValueError):
        Finding("fatal", "x", "y")


def test_finding_equality():
    a = Finding("warn", "c", "m")
    b = Finding("warn", "c", "m")
    assert a == b
