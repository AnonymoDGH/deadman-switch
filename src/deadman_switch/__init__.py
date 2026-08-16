"""Dead Man's Switch — a heartbeat watchdog that fires a payload when you go silent.

The classic spy prop: arm it, keep the heartbeat file fresh, and if you stop
touching it the switch fires — webhook, email, or command.
"""

from __future__ import annotations

import json
import smtplib
import subprocess
import time
import urllib.request
from email.message import EmailMessage
from pathlib import Path

CONFIG_DIR = Path.home() / ".dms"
CONFIG = CONFIG_DIR / "config.json"
DEFAULT_TTL = 86400  # 24h


def default_config() -> dict:
    return {
        "heartbeat": str(CONFIG_DIR / "heartbeat"),
        "ttl_seconds": DEFAULT_TTL,
        "payload": {
            "type": "print",
            "message": "The dead man's switch has fired.",
        },
    }


def load_config(path: Path = CONFIG) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default_config()


def save_config(cfg: dict, path: Path = CONFIG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def heartbeat(path: Path | str | None = None, cfg: dict | None = None) -> Path:
    """Stamp the heartbeat file with the current time."""
    cfg = cfg or load_config()
    hb = Path(path or cfg["heartbeat"])
    hb.parent.mkdir(parents=True, exist_ok=True)
    hb.touch()
    return hb


def last_beat(path: Path | str | None = None, cfg: dict | None = None) -> float | None:
    """mtime of the heartbeat file, or None if it has never beat."""
    cfg = cfg or load_config()
    hb = Path(path or cfg["heartbeat"])
    if not hb.exists():
        return None
    return hb.stat().st_mtime


def age_seconds(path: Path | str | None = None, cfg: dict | None = None) -> float | None:
    last = last_beat(path, cfg)
    return None if last is None else time.time() - last


def fire(payload: dict) -> None:
    """Execute a payload. Types: print | webhook | email | command."""
    kind = payload.get("type", "print")

    if kind == "print":
        print(payload.get("message", "Dead man's switch fired."))

    elif kind == "webhook":
        url = payload["url"]
        data = payload.get("data", "{}").encode()
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)

    elif kind == "email":
        msg = EmailMessage()
        msg["From"] = payload["from"]
        msg["To"] = payload["to"]
        msg["Subject"] = payload.get("subject", "Dead Man's Switch")
        msg.set_content(payload.get("message", "The dead man's switch has fired."))
        with smtplib.SMTP(payload["smtp_host"], payload.get("smtp_port", 587)) as s:
            s.starttls()
            s.login(payload["smtp_user"], payload["smtp_pass"])
            s.send_message(msg)

    elif kind == "command":
        subprocess.run(payload["command"], shell=True, check=False)

    else:
        raise ValueError(f"Unknown payload type: {kind!r}")


def check(path: Path | str | None = None, cfg: dict | None = None) -> bool:
    """One check. Fires (and returns True) if the switch is tripped."""
    cfg = cfg or load_config()
    last = last_beat(path, cfg)
    if last is None or (time.time() - last) > cfg["ttl_seconds"]:
        fire(cfg["payload"])
        return True
    return False


def watch(path: Path | str | None = None, cfg: dict | None = None,
          interval: int = 10) -> None:
    """Block until the switch fires."""
    cfg = cfg or load_config()
    while True:
        if check(path, cfg):
            return
        time.sleep(interval)


__version__ = "0.2.0"

# --- v0.2.0 public API -----------------------------------------------------
# The modules below are the expanded toolkit. They are imported by name so
# that the package exposes them as attributes; use e.g.
#   from deadman_switch.engine import Switch
from . import (  # noqa: E402
    audit, beacon, channels, checklists, clock, contacts, crypto,
    debrief, dispatcher, drill, duress, engine, escrow, events, exporter,
    formats,
    handler, heartbeat as heartbeat_records, inventory, journal, legacy,
    metrics, payloads, policy, proof, quorum, recovery, report, rotation,
    runbook, scenarios, schedule, simulator, state, store, templates,
    timefmt, watchdog,
)

__all__ = [
    "__version__",
    # original v0.1 API
    "CONFIG", "CONFIG_DIR", "DEFAULT_TTL",
    "default_config", "load_config", "save_config",
    "heartbeat", "last_beat", "age_seconds",
    "fire", "check", "watch",
    # v0.2.0 modules
    "audit", "beacon", "channels", "checklists", "clock", "contacts",
    "crypto", "debrief", "dispatcher", "drill", "duress", "engine", "escrow",
    "events",
    "exporter", "formats", "handler", "heartbeat_records", "inventory",
    "journal", "legacy", "metrics", "payloads", "policy", "proof", "quorum",
    "recovery", "report", "rotation", "runbook", "scenarios", "schedule",
    "simulator", "state", "store", "templates", "timefmt", "watchdog",
]
