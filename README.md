<div align="center">

# 🪤 Dead Man's Switch

<img src="https://raw.githubusercontent.com/AnonymoDGH/deadman-switch/main/logo.png" alt="Dead Man's Switch" width="180"/>

**A heartbeat watchdog that fires when you go silent.**

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/badge/PyPI-deadman--switch-orange.svg)](https://pypi.org/project/deadman-switch/)
[![Platform](https://img.shields.io/badge/platform-osx%20%7C%20linux%20%7C%20windows-lightgrey.svg)]()

> *"If I don't check in by tomorrow, the package ships itself."*

</div>

---

## What is it?

The **Dead Man's Switch** is the oldest trick in the espionage playbook, turned
into a tiny command-line tool. You arm it with a TTL (time-to-live). You stamp
a heartbeat file — a proof of life. If the heartbeat goes stale — if you're
taken, you're cut off, or your cron just breaks — the switch fires its payload.

A natural fit for:

- **Novel research** — the scene where the captured hero can't touch the file
  and the countdown is real.
- **Automation safety** — if a scheduled task stops reporting, get an alert.
- **Personal failsafes** — a check-in ritual that escalates when it breaks.

## Features

- ⏱️ Heartbeat file with configurable TTL
- 🔫 Four payload types: `print`, `webhook`, `email`, `command`
- 🌀 Watch mode — blocks and fires the moment the switch trips
- 🛡️ `status` command tells you exactly how much slack you have left
- 📦 Zero runtime dependencies, pure Python standard library

## Install

```bash
pip install deadman-switch
```

From source:

```bash
git clone https://github.com/AnonymoDGH/deadman-switch
cd deadman-switch
pip install -e .
```

## Quickstart

```bash
# 1. Arm it — 60 seconds of silence means fire
dms arm --ttl 60 --payload '{"type": "command", "command": "echo released the files"}'

# 2. Prove you're alive
dms heartbeat

# 3. How much slack is left?
dms status
# [+] Alive. Last beat 3s ago, 57s of slack left.

# 4. Block until the switch fires
dms watch
```

## CLI reference

| Command | What it does |
|---|---|
| `dms init` | Create a default config and first heartbeat |
| `dms arm --ttl <s> --payload <json>` | Set TTL / payload, then beat |
| `dms heartbeat` | Stamp the heartbeat file |
| `dms status` | Report age and whether the switch is tripped |
| `dms watch [--interval <s>]` | Block until the payload fires |
| `dms disarm` | Neuter the payload (safe mode) |

All commands accept `--config <path>` to point at a different config file.

## Payloads

```json
{ "type": "webhook", "url": "https://example.com/hook", "data": "{\"op\":\"release\"}" }
{ "type": "email", "from": "agent@example.com", "to": "control@example.com",
  "subject": "SILENCE", "message": "The package is loose.",
  "smtp_host": "smtp.example.com", "smtp_user": "u", "smtp_pass": "p" }
{ "type": "command", "command": "python notify.py --urgent" }
```

## How it works

<img src="https://raw.githubusercontent.com/AnonymoDGH/deadman-switch/main/assets/architecture.svg" alt="Architecture" width="820"/>

## Tests

```bash
pip install pytest
pytest
```

## License

[MIT](LICENSE) — a fiction research prop. Use it on systems you own, and
keep the fireworks in the novel where they belong.
