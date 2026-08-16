"""Tests for deadman_switch.payloads -- validated payload actions."""

from __future__ import annotations

import pytest

from deadman_switch.payloads import (
    ACTION_TYPES, CommandAction, EmailAction, FileAction, NotifyAction,
    PayloadError, PrintAction, WebhookAction, build_action,
)


def test_build_action_dispatch():
    assert isinstance(build_action({"type": "print"}), PrintAction)
    assert isinstance(build_action({"type": "file", "path": "x"}), FileAction)
    assert isinstance(build_action({"type": "webhook", "url": "http://x"}), WebhookAction)
    assert isinstance(build_action({"type": "command", "command": "echo"}), CommandAction)


def test_build_action_default_is_print():
    assert isinstance(build_action({}), PrintAction)


def test_build_action_unknown_raises():
    with pytest.raises(PayloadError):
        build_action({"type": "teleport"})


def test_print_execute(capsys):
    action = build_action({"type": "print", "message": "BOOM"})
    result = action.execute()
    assert result.ok
    assert "BOOM" in capsys.readouterr().out


def test_print_dry_run_no_output(capsys):
    action = build_action({"type": "print", "message": "BOOM"})
    result = action.dry_run()
    assert result.ok and result.dry_run
    assert capsys.readouterr().out == ""


def test_file_action_writes(tmp_path):
    target = tmp_path / "out" / "msg.txt"
    action = build_action({"type": "file", "path": str(target), "message": "hello"})
    result = action.execute()
    assert result.ok
    assert target.read_text(encoding="utf-8").strip() == "hello"


def test_file_action_requires_path():
    with pytest.raises(PayloadError):
        build_action({"type": "file"})


def test_webhook_requires_valid_url():
    with pytest.raises(PayloadError):
        build_action({"type": "webhook", "url": "ftp://nope"})
    with pytest.raises(PayloadError):
        build_action({"type": "webhook"})


def test_webhook_dry_run_safe_offline():
    action = build_action({"type": "webhook", "url": "http://127.0.0.1:1"})
    result = action.dry_run()
    assert result.ok and result.dry_run


def test_email_requires_fields():
    with pytest.raises(PayloadError):
        build_action({"type": "email", "to": "a@b.c"})  # missing from/host
    action = build_action({"type": "email", "to": "a@b.c",
                           "from": "x@y.z", "smtp_host": "localhost"})
    assert action.dry_run().ok


def test_command_action_success():
    action = build_action({"type": "command", "command": "echo hi"})
    result = action.execute()
    assert result.ok
    assert "exit 0" in result.detail


def test_command_action_failure():
    action = build_action({"type": "command", "command": "exit 3"})
    result = action.execute()
    assert not result.ok
    assert "exit 3" in result.detail


def test_notify_action_records_sink():
    NotifyAction.sink.clear()
    action = build_action({"type": "notify", "label": "test"})
    result = action.execute()
    assert result.ok
    assert NotifyAction.sink[-1]["label"] == "test"


def test_result_to_dict():
    action = build_action({"type": "print"})
    result = action.dry_run()
    d = result.to_dict()
    assert d["action"] == "print"
    assert d["dry_run"] is True


def test_all_types_registered():
    assert set(ACTION_TYPES) == {"print", "file", "webhook", "email",
                                 "command", "notify"}
