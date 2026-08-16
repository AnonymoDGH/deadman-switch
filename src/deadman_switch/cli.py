"""Command-line interface for the Dead Man's Switch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import (
    CONFIG, CONFIG_DIR,
    age_seconds, check, default_config, heartbeat,
    load_config, save_config, watch,
)
from . import formats as formats_mod
from . import recovery as recovery_mod
from . import report as report_mod
from . import simulator as sim_mod
from . import templates as templates_mod
from .beacon import BeaconWatcher, sign_beacon
from .clock import FixedClock
from .engine import Switch, SwitchConfig
from .events import EventLog
from .policy import default_policy
from .state import State


# ---------------------------------------------------------------------------
# original commands (unchanged behavior)
# ---------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> int:
    cfg = default_config()
    save_config(cfg, args.config)
    heartbeat(cfg=cfg)
    print(f"[+] Armed. Config:  {args.config}")
    print(f"[+] Heartbeat: {cfg['heartbeat']}")
    print(f"[+] TTL:       {cfg['ttl_seconds']}s")
    print(f"[+] Payload:   {cfg['payload']['type']}")
    return 0


def cmd_heartbeat(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    hb = heartbeat(cfg=cfg)
    print(f"[+] Heartbeat stamped at {hb}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    age = age_seconds(cfg=cfg)
    if age is None:
        print("[-] Never beat. The switch is TRIPPED.")
    elif age > cfg["ttl_seconds"]:
        print(f"[-] Last beat {age:.0f}s ago (TTL {cfg['ttl_seconds']}s). TRIPPED.")
    else:
        rem = cfg["ttl_seconds"] - age
        print(f"[+] Alive. Last beat {age:.0f}s ago, {rem:.0f}s of slack left.")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    print(f"[*] Watching. Will fire on silence longer than {cfg['ttl_seconds']}s.")
    watch(cfg=cfg, interval=args.interval)
    return 0


def cmd_arm(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    if args.ttl:
        cfg["ttl_seconds"] = args.ttl
    if args.payload:
        try:
            cfg["payload"] = json.loads(args.payload)
        except json.JSONDecodeError as exc:
            print(f"[!] Payload is not valid JSON: {exc}")
            return 1
    save_config(cfg, args.config)
    heartbeat(cfg=cfg)
    print("[+] Armed and beating.")
    return 0


def cmd_disarm(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    cfg["payload"] = {"type": "print", "message": "(disarmed)"}
    save_config(cfg, args.config)
    print("[+] Disarmed. Payload neutered.")
    return 0


# ---------------------------------------------------------------------------
# new commands
# ---------------------------------------------------------------------------

def cmd_simulate(args: argparse.Namespace) -> int:
    """Run a deterministic scenario against the engine."""
    config = SwitchConfig(ttl_seconds=args.ttl, grace_seconds=args.grace)
    if args.scenario == "regular":
        scenario = sim_mod.regular_beats(args.duration, args.beat_interval)
    elif args.scenario == "silence":
        scenario = sim_mod.silence_after(args.duration, args.beat_interval,
                                         silence_from=args.silence_from)
    elif args.scenario == "missed":
        scenario = sim_mod.missed_beat(args.duration, args.beat_interval,
                                       missed_index=args.missed_index)
    else:
        print(f"[!] unknown scenario {args.scenario!r}", file=sys.stderr)
        return 2
    result = sim_mod.run_scenario(config, scenario, tick_interval=args.tick)
    print(f"scenario:     {args.scenario}")
    print(f"duration:     {args.duration}s")
    print(f"final state:  {result.final_state}")
    print(f"fired:        {'yes' if result.fired else 'no'}")
    if result.fired:
        print(f"fired at:     {result.fired_at:.0f}s")
    return 0


def cmd_templates(args: argparse.Namespace) -> int:
    if args.apply:
        try:
            config = templates_mod.apply_template(args.apply)
        except templates_mod.TemplateError as exc:
            print(f"[!] {exc}", file=sys.stderr)
            return 2
        print(formats_mod.to_json(config))
        return 0
    for name in templates_mod.list_templates():
        template = templates_mod.get_template(name)
        print(f"{name:<10} {template['description']}")
        print(f"           ttl={template['ttl_seconds']}s "
              f"grace={template['grace_seconds']}s "
              f"stages={len(template['stages'])}")
    return 0


def cmd_policy(args: argparse.Namespace) -> int:
    policy = default_policy(args.ttl)
    print(f"Escalation policy (base TTL {args.ttl}s):")
    for stage in policy.stages:
        print(f"  {stage.name:<10} after {stage.after_seconds:>8.0f}s  "
              f"-> {stage.payload.get('type')}")
    return 0


def cmd_split(args: argparse.Namespace) -> int:
    secret = args.secret.encode("utf-8")
    try:
        shares = recovery_mod.split_secret(secret, n=args.n, k=args.k)
    except recovery_mod.RecoveryError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 2
    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for share in shares:
            path = out_dir / f"share-{share.x}.txt"
            path.write_text(recovery_mod.serialize_shares([share]) + "\n",
                            encoding="utf-8")
        print(f"[+] Wrote {len(shares)} shares to {out_dir}")
    else:
        print(recovery_mod.serialize_shares(shares))
    print(f"[+] Threshold: any {args.k} of {args.n} shares reconstruct the secret.")
    return 0


def cmd_combine(args: argparse.Namespace) -> int:
    shares = []
    for path in args.share_files:
        try:
            shares.extend(recovery_mod.parse_shares(
                Path(path).read_text(encoding="utf-8")))
        except (OSError, recovery_mod.RecoveryError) as exc:
            print(f"[!] {path}: {exc}", file=sys.stderr)
            return 2
    try:
        secret = recovery_mod.combine_shares(shares)
    except recovery_mod.RecoveryError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 2
    print(secret.decode("utf-8", errors="replace"))
    return 0


def cmd_beacon(args: argparse.Namespace) -> int:
    key = args.key.encode("utf-8")
    beacon = sign_beacon(key, args.switch_id, seq=args.seq, ts=args.ts)
    print(beacon.to_json())
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Render a status report from the current config."""
    cfg = load_config(args.config)
    age = age_seconds(cfg=cfg)
    ttl = cfg["ttl_seconds"]
    grace = cfg.get("grace_seconds", 0)
    if age is None:
        state = State.TRIPPED
        slack = 0.0
    elif age > ttl:
        state = State.TRIPPED
        slack = 0.0
    else:
        state = State.ARMED
        slack = ttl - age
    print(report_mod.status_report(state, age, slack, ttl, grace,
                                   cfg["payload"].get("type", "print")))
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Audit the current config for misconfiguration."""
    from .audit import audit_config
    cfg = load_config(args.config)
    findings = audit_config(cfg)
    if not findings:
        print("[+] Config is clean. No findings.")
        return 0
    for f in findings:
        print(f"[{f.severity.upper():<8}] {f.code}: {f.message}")
    critical = sum(1 for f in findings if f.severity == "critical")
    print(f"\n{len(findings)} finding(s), {critical} critical.")
    return 1 if critical else 0


def cmd_plan(args: argparse.Namespace) -> int:
    """Show a recommended beat schedule for the current TTL."""
    from .schedule import cron_hint, plan_beats
    cfg = load_config(args.config)
    ttl = cfg["ttl_seconds"]
    plan = plan_beats(ttl_seconds=ttl, window_seconds=args.window,
                      safety=args.safety)
    print(f"TTL {ttl}s, safety {args.safety}: beat every {plan.interval:.0f}s")
    print(f"margin per beat: {plan.margin:.0f}s")
    print(f"cron hint: {cron_hint(plan.interval)}")
    print(f"beats over {args.window:.0f}s window: {len(plan)}")
    return 0


def cmd_checklist(args: argparse.Namespace) -> int:
    """Show a pre-flight checklist."""
    from .checklists import get_checklist
    try:
        checklist = get_checklist(args.name)
    except Exception as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 2
    print(checklist.render())
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export the switch state and history in a portable format."""
    from .exporter import export_cheat_sheet, export_json, export_markdown
    from .events import EventLog
    cfg = load_config(args.config)
    log = EventLog()  # CLI export uses a fresh log; store-backed logs go via the API
    if args.format == "json":
        text = export_json("exported", cfg, log, redact=args.redact)
    elif args.format == "markdown":
        text = export_markdown("exported", cfg, log, switch_id=args.switch_id)
    else:
        text = export_cheat_sheet("exported", cfg, switch_id=args.switch_id)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"[+] Export written to {args.out}")
    else:
        print(text)
    return 0


def cmd_runbook(args: argparse.Namespace) -> int:
    """Render the handler runbook for the current config."""
    from .runbook import render_runbook
    cfg = load_config(args.config)
    text = render_runbook(cfg, operator=args.operator)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"[+] Runbook written to {args.out}")
    else:
        print(text)
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    """Show what the configured payload WOULD do, without doing it."""
    from .payloads import build_action
    cfg = load_config(args.config)
    try:
        action = build_action(cfg["payload"])
    except Exception as exc:
        print(f"[!] payload invalid: {exc}", file=sys.stderr)
        return 2
    result = action.dry_run()
    print(f"[dry-run] {result.detail}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="dms",
        description="Dead Man's Switch: fire a payload when the heartbeat goes silent.",
        epilog="Example: dms arm --ttl 60 --payload '{\"type\": \"command\", \"command\": \"echo fired\"}'",
    )
    p.add_argument("--config", default=CONFIG, type=Path,
                   help=f"config file (default: {CONFIG})")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create config + heartbeat").set_defaults(fn=cmd_init)
    sub.add_parser("heartbeat", help="stamp the heartbeat file").set_defaults(fn=cmd_heartbeat)
    sub.add_parser("status", help="check whether the switch is tripped").set_defaults(fn=cmd_status)
    sub.add_parser("disarm", help="neuter the payload").set_defaults(fn=cmd_disarm)

    p_watch = sub.add_parser("watch", help="block until the switch fires")
    p_watch.add_argument("--interval", type=int, default=10, help="poll seconds")
    p_watch.set_defaults(fn=cmd_watch)

    p_arm = sub.add_parser("arm", help="set TTL and/or payload, then beat")
    p_arm.add_argument("--ttl", type=int, help="seconds of silence before firing")
    p_arm.add_argument("--payload", help="JSON payload: type print|webhook|email|command")
    p_arm.set_defaults(fn=cmd_arm)

    p_sim = sub.add_parser("simulate", help="run a deterministic scenario")
    p_sim.add_argument("--scenario", default="regular",
                       choices=["regular", "silence", "missed"])
    p_sim.add_argument("--ttl", type=float, default=60)
    p_sim.add_argument("--grace", type=float, default=0)
    p_sim.add_argument("--duration", type=float, default=300)
    p_sim.add_argument("--beat-interval", type=float, default=30)
    p_sim.add_argument("--silence-from", type=float, default=60)
    p_sim.add_argument("--missed-index", type=int, default=2)
    p_sim.add_argument("--tick", type=float, default=10)
    p_sim.set_defaults(fn=cmd_simulate)

    p_tpl = sub.add_parser("templates", help="list or apply switch templates")
    p_tpl.add_argument("--apply", default=None, help="template name to apply")
    p_tpl.set_defaults(fn=cmd_templates)

    p_pol = sub.add_parser("policy", help="show the default escalation policy")
    p_pol.add_argument("--ttl", type=float, default=3600)
    p_pol.set_defaults(fn=cmd_policy)

    p_split = sub.add_parser("split", help="split a secret into shares")
    p_split.add_argument("secret")
    p_split.add_argument("-n", type=int, required=True, help="total shares")
    p_split.add_argument("-k", type=int, required=True, help="threshold")
    p_split.add_argument("--out-dir", default=None)
    p_split.set_defaults(fn=cmd_split)

    p_combine = sub.add_parser("combine", help="reconstruct a secret from shares")
    p_combine.add_argument("share_files", nargs="+")
    p_combine.set_defaults(fn=cmd_combine)

    p_beacon = sub.add_parser("beacon", help="emit a signed liveness beacon")
    p_beacon.add_argument("--key", required=True)
    p_beacon.add_argument("--switch-id", required=True)
    p_beacon.add_argument("--seq", type=int, required=True)
    p_beacon.add_argument("--ts", type=float, required=True)
    p_beacon.set_defaults(fn=cmd_beacon)

    sub.add_parser("report", help="render a status report").set_defaults(fn=cmd_report)
    sub.add_parser("dry-run", help="show what the payload would do").set_defaults(fn=cmd_dry_run)
    sub.add_parser("audit", help="audit the config for misconfiguration").set_defaults(fn=cmd_audit)

    p_cl = sub.add_parser("checklist", help="show a pre-flight checklist")
    p_cl.add_argument("name", nargs="?", default="pre-arm",
                      help="pre-arm | pre-travel | pre-release")
    p_cl.set_defaults(fn=cmd_checklist)

    p_exp = sub.add_parser("export", help="export switch state/history")
    p_exp.add_argument("--format", default="json",
                       choices=["json", "markdown", "cheat-sheet"])
    p_exp.add_argument("--switch-id", default="switch")
    p_exp.add_argument("--redact", action="store_true")
    p_exp.add_argument("--out", default=None)
    p_exp.set_defaults(fn=cmd_export)

    p_rb = sub.add_parser("runbook", help="render the handler runbook")
    p_rb.add_argument("--operator", default="the operator")
    p_rb.add_argument("--out", default=None, help="write to this file")
    p_rb.set_defaults(fn=cmd_runbook)

    p_plan = sub.add_parser("plan", help="show a recommended beat schedule")
    p_plan.add_argument("--window", type=float, default=86400)
    p_plan.add_argument("--safety", type=float, default=0.5)
    p_plan.set_defaults(fn=cmd_plan)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
