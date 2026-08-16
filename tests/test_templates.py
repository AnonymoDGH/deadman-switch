"""Tests for deadman_switch.templates -- preset switch configurations."""

from __future__ import annotations

import pytest

from deadman_switch.templates import (
    TEMPLATES, TemplateError, apply_template, get_template, list_templates,
    template_to_policy,
)


def test_list_templates():
    names = list_templates()
    assert names == sorted(names)
    assert "daytrip" in names
    assert "legacy" in names


def test_get_template():
    t = get_template("travel")
    assert t["ttl_seconds"] == 24 * 3600
    assert t["stages"]


def test_get_unknown_raises():
    with pytest.raises(TemplateError):
        get_template("nonexistent")


def test_apply_template_shape():
    config = apply_template("daytrip")
    assert config["template"] == "daytrip"
    assert config["ttl_seconds"] == 6 * 3600
    assert config["grace_seconds"] == 2 * 3600
    assert config["payload"]["type"] == "print"


def test_apply_template_overrides():
    config = apply_template("daytrip", overrides={"ttl_seconds": 999})
    assert config["ttl_seconds"] == 999


def test_apply_template_unknown_raises():
    with pytest.raises(TemplateError):
        apply_template("nope")


def test_every_template_builds_policy():
    for name in list_templates():
        policy = template_to_policy(get_template(name))
        assert len(policy) >= 2


def test_template_policy_thresholds_scale_with_ttl():
    t = get_template("daytrip")
    policy = template_to_policy(t)
    thresholds = [s.after_seconds for s in policy.stages]
    assert thresholds == sorted(thresholds)
    assert thresholds[0] == t["ttl_seconds"]


def test_legacy_final_stage_is_file():
    config = apply_template("legacy")
    assert config["payload"]["type"] == "file"


def test_templates_have_descriptions():
    for name in list_templates():
        assert TEMPLATES[name]["description"]
