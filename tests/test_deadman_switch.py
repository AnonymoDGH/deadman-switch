import json
import time

import pytest

from deadman_switch import (
    age_seconds, check, default_config, fire, heartbeat,
    last_beat, load_config, save_config,
)


def make_cfg(tmp_path, ttl=2):
    cfg = default_config()
    cfg["heartbeat"] = str(tmp_path / "heartbeat")
    cfg["ttl_seconds"] = ttl
    cfg["payload"] = {"type": "print", "message": "FIRED"}
    return cfg


def test_heartbeat_stamps_file(tmp_path):
    cfg = make_cfg(tmp_path)
    hb = heartbeat(cfg=cfg)
    assert hb.exists()
    assert last_beat(cfg=cfg) is not None


def test_age_seconds(tmp_path):
    cfg = make_cfg(tmp_path)
    heartbeat(cfg=cfg)
    time.sleep(1.01)
    age = age_seconds(cfg=cfg)
    assert age is not None and age >= 1.0


def test_check_does_not_fire_within_ttl(tmp_path, capsys):
    cfg = make_cfg(tmp_path, ttl=60)
    heartbeat(cfg=cfg)
    assert check(cfg=cfg) is False
    assert "FIRED" not in capsys.readouterr().out


def test_check_fires_when_stale(tmp_path, capsys):
    cfg = make_cfg(tmp_path, ttl=1)
    heartbeat(cfg=cfg)
    time.sleep(1.2)
    assert check(cfg=cfg) is True
    assert "FIRED" in capsys.readouterr().out


def test_check_fires_when_never_beat(tmp_path, capsys):
    cfg = make_cfg(tmp_path)
    assert check(cfg=cfg) is True
    assert "FIRED" in capsys.readouterr().out


def test_config_roundtrip(tmp_path):
    cfg = make_cfg(tmp_path)
    path = tmp_path / "config.json"
    save_config(cfg, path)
    assert load_config(path) == cfg


def test_fire_command_payload(tmp_path):
    log = tmp_path / "fired.txt"
    payload = {"type": "command", "command": f"echo bang > {log}"}
    fire(payload)
    assert log.exists()


def test_fire_unknown_payload_raises():
    with pytest.raises(ValueError):
        fire({"type": "teleport"})
