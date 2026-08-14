"""Command-line interface for the Dead Man's Switch."""

from __future__ import annotations

import argparse
import json
import sys

from . import (
    CONFIG, CONFIG_DIR,
    age_seconds, check, default_config, heartbeat,
    load_config, save_config, watch,
)


def cmd_init(args: argparse.Namespace) -> None:
    cfg = default_config()
    save_config(cfg, args.config)
    heartbeat(cfg=cfg)
    print(f"[+] Armed. Config:  {args.config}")
    print(f"[+] Heartbeat: {cfg['heartbeat']}")
    print(f"[+] TTL:       {cfg['ttl_seconds']}s")
    print(f"[+] Payload:   {cfg['payload']['type']}")


def cmd_heartbeat(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    hb = heartbeat(cfg=cfg)
    print(f"[+] Heartbeat stamped at {hb}")


def cmd_status(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    age = age_seconds(cfg=cfg)
    if age is None:
        print("[-] Never beat. The switch is TRIPPED.")
    elif age > cfg["ttl_seconds"]:
        print(f"[-] Last beat {age:.0f}s ago (TTL {cfg['ttl_seconds']}s). TRIPPED.")
    else:
        rem = cfg["ttl_seconds"] - age
        print(f"[+] Alive. Last beat {age:.0f}s ago, {rem:.0f}s of slack left.")


def cmd_watch(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    print(f"[*] Watching. Will fire on silence longer than {cfg['ttl_seconds']}s.")
    watch(cfg=cfg, interval=args.interval)


def cmd_arm(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    if args.ttl:
        cfg["ttl_seconds"] = args.ttl
    if args.payload:
        try:
            cfg["payload"] = json.loads(args.payload)
        except json.JSONDecodeError as exc:
            print(f"[!] Payload is not valid JSON: {exc}")
            sys.exit(1)
    save_config(cfg, args.config)
    heartbeat(cfg=cfg)
    print("[+] Armed and beating.")


def cmd_disarm(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    cfg["payload"] = {"type": "print", "message": "(disarmed)"}
    save_config(cfg, args.config)
    print("[+] Disarmed. Payload neutered.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="dms",
        description="Dead Man's Switch: fire a payload when the heartbeat goes silent.",
        epilog="Example: dms arm --ttl 60 --payload '{\"type\": \"command\", \"command\": \"echo fired\"}'",
    )
    p.add_argument("--config", default=CONFIG,
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

    args = p.parse_args(argv)
    args.fn(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
