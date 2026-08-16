"""End-to-end integration tests across the deadman-switch package.

These tests exercise the full pipeline the way a handler actually would:
arm a switch, beat it, let it lapse, watch it escalate, fire the payload,
persist and restore it, and audit the event log. They exist to catch
cross-module drift that unit tests miss.
"""

from __future__ import annotations

from pathlib import Path

from deadman_switch.beacon import BeaconWatcher, sign_beacon
from deadman_switch.channels import DeliveryQueue, FileChannel
from deadman_switch.clock import FixedClock
from deadman_switch.crypto import derive_key, sign_cancel, verify_cancel
from deadman_switch.engine import Switch, SwitchConfig
from deadman_switch.events import EventLog
from deadman_switch.metrics import heartbeat_report
from deadman_switch.policy import default_policy
from deadman_switch.proof import ProofOfLife
from deadman_switch.quorum import Approval, Quorum
from deadman_switch.recovery import combine_shares, split_secret
from deadman_switch.report import postmortem_report, status_report
from deadman_switch.simulator import run_scenario, silence_after
from deadman_switch.state import State
from deadman_switch.store import SwitchStore
from deadman_switch.watchdog import Watchdog


def test_full_lifecycle_with_grace_and_rescue():
    """Arm, lapse into warning, rescue, lapse again, fire."""
    clock = FixedClock(start=0.0)
    config = SwitchConfig(ttl_seconds=60, grace_seconds=30)
    fired = []
    sw = Switch(config, clock=clock, on_fire=lambda: fired.append(1),
                payload={"type": "notify", "label": "it"})
    sw.arm()

    clock.advance(61)
    assert sw.tick() == State.WARNING

    sw.beat()  # rescued
    assert sw.state == State.ARMED

    clock.advance(61)
    sw.tick()  # WARNING again
    clock.advance(31)
    assert sw.tick() == State.TRIPPED

    clock.advance(1)
    assert sw.tick() == State.FIRED
    assert fired == [1]
    assert sw.log.verify() is True


def test_persist_restore_and_postmortem(tmp_path):
    """Fire a switch, persist it, restore it, and render a post-mortem."""
    clock = FixedClock(start=0.0)
    config = SwitchConfig(ttl_seconds=60)
    sw = Switch(config, clock=clock,
                payload={"type": "notify", "label": "it"})
    sw.arm()
    clock.advance(61)
    sw.tick()
    assert sw.state == State.FIRED

    store = SwitchStore(tmp_path / "store")
    sw.save(store)
    restored = Switch.load(store, clock=FixedClock(start=1000.0))
    assert restored.state == State.FIRED
    assert restored.log.verify() is True

    text = postmortem_report(restored.log, restored.state)
    assert "fired:        yes" in text


def test_authenticated_cancel_flow():
    """Trip the switch, then cancel it with a signed token."""
    key, _ = derive_key("cancel-secret")
    clock = FixedClock(start=0.0)
    config = SwitchConfig(ttl_seconds=60, grace_seconds=30)
    sw = Switch(config, clock=clock)
    sw.arm()
    clock.advance(61)
    sw.tick()   # WARNING
    clock.advance(31)
    sw.tick()   # TRIPPED

    token = sign_cancel(key, "switch-1", timestamp=clock.now())
    assert verify_cancel(key, token, "switch-1") is True
    sw.cancel()
    assert sw.state == State.DISARMED


def test_recovery_split_and_cancel():
    """Split the disarm key, reconstruct from a quorum of shares."""
    secret = b"disarm-key-xyz"
    shares = split_secret(secret, n=3, k=2)
    recovered = combine_shares(shares[:2])
    assert recovered == secret


def test_quorum_cancel_gating():
    """A cancel only proceeds once the quorum of parties approves."""
    q = Quorum("switch-1", threshold=2, parties=["alice", "bob", "carol"])
    q.begin_round()
    assert q.cast(Approval("alice", "switch-1", q.round)) is False
    assert q.cast(Approval("bob", "switch-1", q.round)) is True
    assert q.is_met() is True


def test_proof_of_life_gates_heartbeat():
    """A beat only counts if the operator answers the challenge."""
    pol = ProofOfLife(seed=7)
    challenge = pol.issue("arithmetic")
    result = pol.answer(challenge.answer)
    assert result.correct is True
    assert pol.is_coerced() is False


def test_beacon_watchdog_mirror():
    """The watcher side detects silence, mirroring the switch."""
    key, _ = derive_key("beacon-key")
    watcher = BeaconWatcher(key, "switch-1")
    watcher.receive(sign_beacon(key, "switch-1", 1, 1000.0))
    assert watcher.is_overdue(now=1030.0, max_age=60) is False
    assert watcher.is_overdue(now=1061.0, max_age=60) is True


def test_delivery_queue_on_fire(tmp_path):
    """When the switch fires, the alert is queued and delivered."""
    channel = FileChannel(tmp_path / "alerts.jsonl")
    queue = DeliveryQueue([channel])

    clock = FixedClock(start=0.0)
    config = SwitchConfig(ttl_seconds=60)
    sw = Switch(config, clock=clock,
                on_fire=lambda: queue.deliver("switch fired"))
    sw.arm()
    clock.advance(61)
    sw.tick()
    queue.flush()
    assert queue.delivered == ["switch fired"]
    assert (tmp_path / "alerts.jsonl").exists()


def test_watchdog_fleet_scenario():
    """A fleet of switches on a shared clock; only the lapsed one fires."""
    wd = Watchdog(clock=FixedClock(start=0.0))
    wd.add("short", SwitchConfig(ttl_seconds=60))
    wd.add("long", SwitchConfig(ttl_seconds=300))
    wd.arm_all()
    wd.clock.advance(70)
    states = wd.tick_all()
    assert states["short"] == State.FIRED
    assert states["long"] == State.ARMED
    assert wd.fired() == ["short"]


def test_simulate_then_report():
    """Simulate a silence scenario and render its status."""
    config = SwitchConfig(ttl_seconds=60)
    scenario = silence_after(300, interval=30, silence_from=60)
    result = run_scenario(config, scenario, tick_interval=10)
    assert result.fired is True
    text = status_report(result.final_state, age=None, slack=0,
                         ttl_seconds=60)
    assert "FIRED" in text


def test_heartbeat_metrics_from_beats():
    """Beat timestamps feed the regularity metrics."""
    beats = [0, 30, 60, 90, 120]
    report = heartbeat_report(beats, expected_interval=30)
    assert report["punctuality"]["score"] == 1.0
    assert report["stats"]["jitter"] == 0


def test_policy_drives_escalation():
    """The default policy's thresholds line up with the TTL multiples."""
    policy = default_policy(60)
    assert [s.name for s in policy.reached(60)] == ["remind"]
    assert [s.name for s in policy.reached(120)] == ["remind", "alert"]
    assert [s.name for s in policy.reached(180)] == ["remind", "alert", "release"]
