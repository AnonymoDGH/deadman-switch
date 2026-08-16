"""Tabletop threat scenarios for handler training.

A switch is only as good as the people running it. Before trusting one in
the field, the handler team should walk through realistic what-ifs: the
operator is detained, the heartbeat file is tampered with, a contact goes
rogue, the network is down for days. This module encodes a library of those
scenarios as structured data, each with a narrative, the expected switch
behavior, and the correct handler response.

Scenarios are used two ways: as documentation (render them into the
runbook or a training sheet) and as executable checks (each scenario names
the state the switch should end in, so a test harness can assert the switch
behaved correctly). The library is deliberately a mix of technical failures
and human/adversarial pressure, because both are what handlers actually
face.
"""

from __future__ import annotations

from typing import Dict, List, Optional

__all__ = [
    "ScenarioError",
    "ThreatScenario",
    "SCENARIOS",
    "list_scenarios",
    "get_scenario",
    "render_scenario_sheet",
]


class ScenarioError(ValueError):
    """Raised for scenario misuse."""


class ThreatScenario:
    """One tabletop scenario."""

    def __init__(self, name: str, narrative: str, expected_state: str,
                 handler_response: List[str],
                 tags: Optional[List[str]] = None) -> None:
        if not name.strip():
            raise ScenarioError("scenario name must not be empty")
        if not narrative.strip():
            raise ScenarioError("narrative must not be empty")
        if not handler_response:
            raise ScenarioError("handler_response must not be empty")
        self.name = name.strip()
        self.narrative = narrative.strip()
        self.expected_state = expected_state
        self.handler_response = list(handler_response)
        self.tags = [t.strip().lower() for t in (tags or []) if t.strip()]

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "narrative": self.narrative,
            "expected_state": self.expected_state,
            "handler_response": self.handler_response,
            "tags": self.tags,
        }


SCENARIOS: Dict[str, ThreatScenario] = {}


def _register(scenario: ThreatScenario) -> None:
    SCENARIOS[scenario.name] = scenario


_register(ThreatScenario(
    name="detained-operator",
    narrative=("The operator is detained and cannot beat. Their devices are"
               "seized, so no heartbeat arrives and none can be faked."
               "The switch must run its full escalation to fire."),
    expected_state="fired",
    handler_response=[
        "Confirm detention through an independent channel.",
        "Do NOT cancel on any request that arrives via the operator's own"
        "seized devices.",
        "Let the switch fire; execute the payload follow-up plan.",
    ],
    tags=["adversarial", "detention"],
))

_register(ThreatScenario(
    name="heartbeat-tamper",
    narrative=("An adversary who found the heartbeat file keeps touching it"
               "to keep the switch alive while the operator is actually gone."),
    expected_state="armed",
    handler_response=[
        "Rely on signed heartbeat records, not a bare file touch.",
        "Issue a proof-of-life challenge; a file-toucher cannot answer it.",
        "If the challenge fails or goes unanswered, treat the operator as"
        "gone and proceed toward cancel/fire by policy.",
    ],
    tags=["adversarial", "tamper"],
))

_register(ThreatScenario(
    name="rogue-contact",
    narrative=("A trusted contact goes rogue and tries to cancel the switch"
               "early to suppress the payload."),
    expected_state="tripped",
    handler_response=[
        "Require a signed cancel token; a rogue contact without the key"
        "cannot produce one.",
        "If a quorum is configured, one rogue member cannot reach threshold.",
        "Rotate the disarm key shares after any suspected compromise.",
    ],
    tags=["insider", "cancel"],
))

_register(ThreatScenario(
    name="network-outage",
    narrative=("A multi-day network outage prevents the operator's beat from"
               "reaching the switch, though the operator is safe."),
    expected_state="warning",
    handler_response=[
        "The grace period should absorb a short outage; verify the TTL and"
        "grace are sized for the operator's environment.",
        "Contact the operator via an out-of-band channel before acting.",
        "If the operator confirms safety, cancel or extend; do not fire.",
    ],
    tags=["environmental", "outage"],
))

_register(ThreatScenario(
    name="duress-beat",
    narrative=("The operator is coerced into beating the switch to hide their"
               "situation. The beat looks normal but carries a duress flag."),
    expected_state="armed",
    handler_response=[
        "The proof-of-life duress answer covertly flags coercion."
        "Treat a duress flag as the operator NOT being safe, despite the beat.",
        "Escalate quietly; do not alert the coercer via the switch state.",
    ],
    tags=["adversarial", "duress"],
))

_register(ThreatScenario(
    name="forgotten-switch",
    narrative=("A switch with a very long TTL is armed and then forgotten by"
               "everyone. Months later it is still armed with a live payload."),
    expected_state="armed",
    handler_response=[
        "Audit flags TTLs longer than a year as ttl-very-long."
        "Keep an inventory of all armed switches and review it on a"
        "schedule.",
        "Disarm any switch whose purpose has lapsed.",
    ],
    tags=["operational", "hygiene"],
))


def list_scenarios() -> List[str]:
    """The names of all scenarios, sorted."""
    return sorted(SCENARIOS)


def get_scenario(name: str) -> ThreatScenario:
    """Fetch one scenario by name."""
    if name not in SCENARIOS:
        raise ScenarioError(
            f"unknown scenario {name!r}; choose from {list_scenarios()}")
    return SCENARIOS[name]


def render_scenario_sheet(names: Optional[List[str]] = None) -> str:
    """Render one or all scenarios as a training sheet."""
    selected = names or list_scenarios()
    lines: List[str] = ["# Tabletop Threat Scenarios", ""]
    for name in selected:
        scenario = get_scenario(name)
        lines.append(f"## {scenario.name}")
        lines.append("")
        lines.append(scenario.narrative)
        lines.append("")
        lines.append(f"Expected switch state: **{scenario.expected_state}**")
        lines.append("")
        lines.append("Handler response:")
        for step in scenario.handler_response:
            lines.append(f"- {step}")
        if scenario.tags:
            lines.append("")
            lines.append(f"Tags: {', '.join(scenario.tags)}")
        lines.append("")
    return "\n".join(lines)
