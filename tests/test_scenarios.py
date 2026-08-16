"""Tests for deadman_switch.scenarios -- tabletop threat scenarios."""

from __future__ import annotations

import pytest

from deadman_switch.scenarios import (
    SCENARIOS, ScenarioError, ThreatScenario, get_scenario, list_scenarios,
    render_scenario_sheet,
)


def test_library_not_empty():
    assert len(list_scenarios()) >= 6


def test_list_sorted():
    names = list_scenarios()
    assert names == sorted(names)


def test_get_scenario():
    scenario = get_scenario("detained-operator")
    assert scenario.expected_state == "fired"
    assert scenario.handler_response


def test_get_unknown_raises():
    with pytest.raises(ScenarioError):
        get_scenario("nonexistent")


def test_every_scenario_has_required_fields():
    for name in list_scenarios():
        scenario = get_scenario(name)
        assert scenario.narrative
        assert scenario.expected_state
        assert scenario.handler_response


def test_scenario_validation():
    with pytest.raises(ScenarioError):
        ThreatScenario("  ", "narrative", "fired", ["step"])
    with pytest.raises(ScenarioError):
        ThreatScenario("x", "  ", "fired", ["step"])
    with pytest.raises(ScenarioError):
        ThreatScenario("x", "narrative", "fired", [])


def test_to_dict():
    scenario = get_scenario("rogue-contact")
    data = scenario.to_dict()
    assert data["name"] == "rogue-contact"
    assert data["expected_state"] == "tripped"
    assert "insider" in data["tags"]


def test_render_sheet_all():
    text = render_scenario_sheet()
    assert "# Tabletop Threat Scenarios" in text
    for name in list_scenarios():
        assert f"## {name}" in text


def test_render_sheet_subset():
    text = render_scenario_sheet(["duress-beat"])
    assert "## duress-beat" in text
    assert "## rogue-contact" not in text


def test_render_sheet_unknown_raises():
    with pytest.raises(ScenarioError):
        render_scenario_sheet(["bogus"])


def test_render_sheet_includes_response():
    text = render_scenario_sheet(["network-outage"])
    assert "Handler response:" in text
    assert "grace" in text.lower()
