<div align="center">

# 🪤 Dead Man's Switch

<img src="https://raw.githubusercontent.com/AnonymoDGH/deadman-switch/main/logo.png" alt="Dead Man's Switch" width="180"/>

**A heartbeat watchdog that fires when you go silent — now a full handler toolkit.**

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/badge/PyPI-deadman--switch-orange.svg)](https://pypi.org/project/deadman-switch/)
[![Platform](https://img.shields.io/badge/platform-osx%20%7C%20linux%20%7C%20windows-lightgrey.svg)]()

> *"If I don't check in by tomorrow, the package ships itself."*

</div>

---

## What is it?

The **Dead Man's Switch** is the oldest trick in the espionage playbook, turned
into a command-line toolkit. You arm it with a TTL (time-to-live). You stamp a
heartbeat — a proof of life. If the heartbeat goes stale — if you're taken,
you're cut off, or your cron just breaks — the switch escalates and fires its
payload.

**v0.2.0** grows the prop into the whole apparatus around it: a deterministic
engine with a grace/warning phase, a tamper-evident event log, signed
heartbeats and cancel tokens, proof-of-life challenges with a covert duress
flag, Shamir secret sharing for the disarm key, quorum cancel approval,
escalation policies, delivery channels with retry, a contact roster, a
scenario simulator, handler reporting, and pre-flight checklists.

A natural fit for:

- **Novel research** — the scene where the captured hero can't touch the file
  and the countdown is real.
- **Automation safety** — if a scheduled task stops reporting, get an alert.
- **Personal failsafes** — a check-in ritual that escalates when it breaks.

## Features

- ⏱️ Heartbeat with configurable TTL **and grace/warning phase**
- 🔫 Six payload types: `print`, `webhook`, `email`, `command`, `file`, `notify`
- 🧾 **Tamper-evident event log** (SHA-256 hash chain)
- 🔐 **Signed heartbeats & cancel tokens** (HMAC, replay-protected)
- 🧠 **Proof-of-life challenges** with a covert **duress** answer
- 🗝️ **Shamir secret sharing** to split the disarm key among trusted parties
- 👥 **Quorum cancel** — M-of-N approvals before a cancel is honored
- 📈 **Escalation policies** — remind → alert → release on a schedule
- 📡 **Delivery channels** with retry queue (file + loopback UDP)
- 🧪 **Scenario simulator** — replay beat patterns on a deterministic clock
- 📋 **Handler reporting** — status, timeline, post-mortem, runbook, debrief
- ✅ **Pre-flight checklists** and **config auditing**
- 🕯️ **Digital legacy planner** — staged, gated release of assets
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

All commands accept `--config <path>` to point at a different config file.

| Command | What it does |
|---|---|
| `dms init` | Create a default config and first heartbeat |
| `dms arm --ttl <s> --payload <json>` | Set TTL / payload, then beat |
| `dms heartbeat` | Stamp the heartbeat file |
| `dms status` | Report age and whether the switch is tripped |
| `dms watch [--interval <s>]` | Block until the payload fires |
| `dms disarm` | Neuter the payload (safe mode) |
| `dms report` | Render a live status report |
| `dms dry-run` | Show what the payload would do, without doing it |
| `dms audit` | Audit the config for misconfiguration |
| `dms plan [--window <s>] [--safety <f>]` | Recommend a beat schedule |
| `dms runbook [--out <file>]` | Render the handler runbook |
| `dms checklist [pre-arm\|pre-travel\|pre-release]` | Show a pre-flight checklist |
| `dms templates [--apply <name>]` | List or apply switch templates |
| `dms policy [--ttl <s>]` | Show the default escalation policy |
| `dms simulate --scenario <regular\|silence\|missed>` | Run a deterministic scenario |
| `dms split <secret> -n <N> -k <K> [--out-dir <d>]` | Split a secret into shares |
| `dms combine <share-files...>` | Reconstruct a secret from shares |
| `dms beacon --key <k> --switch-id <id> --seq <n> --ts <t>` | Emit a signed liveness beacon |
| `dms export --format <json\|markdown\|cheat-sheet>` | Export switch state/history |

## Payloads

```json
{ "type": "webhook", "url": "https://example.com/hook", "data": "{\"op\":\"release\"}" }
{ "type": "email", "from": "agent@example.com", "to": "control@example.com",
  "subject": "SILENCE", "message": "The package is loose.",
  "smtp_host": "smtp.example.com", "smtp_user": "u", "smtp_pass": "p" }
{ "type": "command", "command": "python notify.py --urgent" }
{ "type": "file", "path": "release.txt", "message": "..." }
{ "type": "notify", "label": "trusted-contact" }
```

## The handler toolkit (v0.2.0)

The package is organized as small, testable modules you can compose:

| Module | Purpose |
|---|---|
| `engine` | Deterministic switch state machine (arm/beat/warn/trip/fire) |
| `state` | The switch lifecycle FSM |
| `events` | Tamper-evident hash-chained event log |
| `clock` | Injectable clocks (`FixedClock`) for deterministic tests |
| `store` | Atomic on-disk persistence of state + log |
| `payloads` | The six payload actions + `dry_run` |
| `policy` | Escalation policies (remind/alert/release) |
| `crypto` | PBKDF2 keys, signed heartbeats & cancel tokens |
| `proof` | Proof-of-life challenges + duress flag |
| `duress` | Spoken duress code pairs |
| `recovery` | Shamir secret sharing for the disarm key |
| `quorum` | M-of-N cancel approval |
| `beacon` | Signed outbound liveness beacons + watcher |
| `heartbeat` | Signed heartbeat records + ledger |
| `channels` | Delivery channels (file, loopback UDP) + retry queue |
| `contacts` | Trusted contact roster with clearance + rotation |
| `dispatcher` | Routes alerts to contacts by escalation level |
| `simulator` | Deterministic scenario replay |
| `schedule` | Beat schedule planning + cron hints |
| `metrics` | Heartbeat regularity (jitter, punctuality) |
| `watchdog` | Multi-switch fleet manager on a shared clock |
| `handler` | Mission-control orchestrator for one switch |
| `audit` | Config security linting |
| `checklists` | Pre-arm / pre-travel / pre-release checklists |
| `templates` | Preset switch configurations |
| `scenarios` | Tabletop threat scenarios for training |
| `report` / `runbook` / `debrief` / `exporter` | Handler documentation |
| `escrow` | Encrypted payload escrow released on fire |
| `legacy` | Staged digital-legacy release planner |
| `inventory` | Registry of all switches (anti-forgotten-switch) |
| `rotation` | Key/token rotation scheduling |
| `journal` | Operator journal attached to beats |
| `formats` / `timefmt` | Serialization + human-friendly time |

### Example: simulate a silence scenario

```bash
dms simulate --scenario silence --ttl 60 --duration 300 \
             --beat-interval 30 --silence-from 60
# scenario:     silence
# final state:  fired
# fired:        yes
```

### Example: split the disarm key

```bash
dms split "my-disarm-key" -n 3 -k 2 --out-dir ./shares
dms combine ./shares/share-1.txt ./shares/share-3.txt
```

## How it works

<img src="https://raw.githubusercontent.com/AnonymoDGH/deadman-switch/main/assets/architecture.svg" alt="Architecture" width="820"/>

## Tests

```bash
pip install pytest
pytest
```

The suite is fully deterministic: the engine runs on an injected `FixedClock`,
network tests use loopback UDP, and there are no external services.

## License

[MIT](LICENSE) — a fiction research prop. Use it on systems you own, and
keep the fireworks in the novel where they belong.
