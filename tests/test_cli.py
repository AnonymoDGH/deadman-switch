"""Tests for the expanded dms CLI."""

from __future__ import annotations

import json

import pytest

from deadman_switch.cli import main


@pytest.fixture
def cfg_file(tmp_path):
    """A config file pointed at a temp heartbeat."""
    path = tmp_path / "config.json"
    cfg = {
        "heartbeat": str(tmp_path / "heartbeat"),
        "ttl_seconds": 60,
        "payload": {"type": "print", "message": "FIRED"},
    }
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


def test_init(tmp_path, capsys):
    cfg = tmp_path / "config.json"
    assert main(["--config", str(cfg), "init"]) == 0
    out = capsys.readouterr().out
    assert "Armed" in out
    assert cfg.exists()


def test_heartbeat_and_status(cfg_file, capsys):
    assert main(["--config", str(cfg_file), "heartbeat"]) == 0
    capsys.readouterr()
    assert main(["--config", str(cfg_file), "status"]) == 0
    out = capsys.readouterr().out
    assert "Alive" in out


def test_arm_sets_ttl(cfg_file, capsys):
    assert main(["--config", str(cfg_file), "arm", "--ttl", "120"]) == 0
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert cfg["ttl_seconds"] == 120


def test_arm_bad_payload(cfg_file, capsys):
    rc = main(["--config", str(cfg_file), "arm", "--payload", "{not json"])
    assert rc == 1


def test_disarm(cfg_file, capsys):
    assert main(["--config", str(cfg_file), "disarm"]) == 0
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert cfg["payload"]["message"] == "(disarmed)"


def test_simulate_regular(capsys):
    assert main(["simulate", "--scenario", "regular", "--ttl", "60",
                 "--duration", "200", "--beat-interval", "30"]) == 0
    out = capsys.readouterr().out
    assert "fired:        no" in out


def test_simulate_silence_fires(capsys):
    assert main(["simulate", "--scenario", "silence", "--ttl", "60",
                 "--duration", "300", "--beat-interval", "30",
                 "--silence-from", "60"]) == 0
    out = capsys.readouterr().out
    assert "fired:        yes" in out


def test_templates_list(capsys):
    assert main(["templates"]) == 0
    out = capsys.readouterr().out
    assert "daytrip" in out
    assert "legacy" in out


def test_templates_apply(capsys):
    assert main(["templates", "--apply", "daytrip"]) == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["template"] == "daytrip"


def test_templates_apply_unknown(capsys):
    rc = main(["templates", "--apply", "nope"])
    assert rc == 2


def test_policy(capsys):
    assert main(["policy", "--ttl", "100"]) == 0
    out = capsys.readouterr().out
    assert "remind" in out
    assert "release" in out


def test_split_and_combine_roundtrip(tmp_path, capsys):
    out_dir = tmp_path / "shares"
    assert main(["split", "my-secret", "-n", "3", "-k", "2",
                 "--out-dir", str(out_dir)]) == 0
    capsys.readouterr()
    share_files = sorted(str(p) for p in out_dir.glob("share-*.txt"))[:2]
    assert main(["combine", *share_files]) == 0
    out = capsys.readouterr().out
    assert "my-secret" in out


def test_split_invalid(capsys):
    rc = main(["split", "s", "-n", "2", "-k", "3"])
    assert rc == 2


def test_beacon(capsys):
    assert main(["beacon", "--key", "k", "--switch-id", "s",
                 "--seq", "1", "--ts", "1000"]) == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["switch_id"] == "s"
    assert parsed["seq"] == 1


def test_report(cfg_file, capsys):
    main(["--config", str(cfg_file), "heartbeat"])
    capsys.readouterr()
    assert main(["--config", str(cfg_file), "report"]) == 0
    out = capsys.readouterr().out
    assert "STATUS" in out


def test_dry_run(cfg_file, capsys):
    assert main(["--config", str(cfg_file), "dry-run"]) == 0
    out = capsys.readouterr().out
    assert "[dry-run]" in out
    assert "would print" in out

def test_audit_clean(cfg_file, capsys):
    assert main(["--config", str(cfg_file), "audit"]) == 0
    out = capsys.readouterr().out
    assert "clean" in out


def test_audit_critical(tmp_path, capsys):
    import json as _json
    path = tmp_path / "bad.json"
    path.write_text(_json.dumps({"ttl_seconds": -1,
                                 "payload": {"type": "bogus"}}),
                    encoding="utf-8")
    rc = main(["--config", str(path), "audit"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "CRITICAL" in out


def test_plan(cfg_file, capsys):
    assert main(["--config", str(cfg_file), "plan", "--window", "3600"]) == 0
    out = capsys.readouterr().out
    assert "cron hint" in out
    assert "margin per beat" in out
