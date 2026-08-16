"""Preset switch templates for common scenarios.

Configuring a switch from scratch every time is error-prone. Most real uses
fall into a handful of shapes: a short trip where you check in daily, a
longer deployment with a generous grace period, a medical scenario where a
trusted contact should be alerted quickly, or a digital-legacy release that
should only happen after a long, unambiguous silence.

This module encodes those shapes as named templates. Each template is a
plain dict describing TTL, grace period, escalation policy, and a suggested
payload, so a handler can instantiate one, tweak it, and arm it. Templates
are validated when applied so a broken preset is caught immediately.
"""

from __future__ import annotations

from typing import Dict, List

from .policy import EscalationPolicy, PolicyError, Stage

__all__ = [
    "TemplateError",
    "TEMPLATES",
    "list_templates",
    "get_template",
    "apply_template",
    "template_to_policy",
]


class TemplateError(ValueError):
    """Raised for unknown or malformed templates."""


#: Named templates. ttl/grace in seconds; stages as (name, multiplier, payload).
TEMPLATES: Dict[str, Dict] = {
    "daytrip": {
        "description": "Short outing; check in every few hours, fire same day.",
        "ttl_seconds": 6 * 3600,
        "grace_seconds": 2 * 3600,
        "stages": [
            ("remind", 1.0, {"type": "print",
                             "message": "Day-trip heartbeat overdue."}),
            ("alert", 2.0, {"type": "notify", "label": "trusted-contact"}),
            ("release", 3.0, {"type": "print",
                              "message": "Day-trip switch fired."}),
        ],
    },
    "travel": {
        "description": "Multi-day travel with spotty signal; generous slack.",
        "ttl_seconds": 24 * 3600,
        "grace_seconds": 12 * 3600,
        "stages": [
            ("remind", 1.0, {"type": "print",
                             "message": "Travel heartbeat overdue."}),
            ("alert", 2.0, {"type": "notify", "label": "trusted-contact"}),
            ("release", 4.0, {"type": "print",
                              "message": "Travel switch fired."}),
        ],
    },
    "medical": {
        "description": "Health watch; alert a contact quickly, short fuse.",
        "ttl_seconds": 4 * 3600,
        "grace_seconds": 1 * 3600,
        "stages": [
            ("alert", 1.0, {"type": "notify", "label": "emergency-contact"}),
            ("release", 2.0, {"type": "print",
                              "message": "Medical switch fired."}),
        ],
    },
    "legacy": {
        "description": "Digital legacy; release only after a long silence.",
        "ttl_seconds": 30 * 24 * 3600,
        "grace_seconds": 7 * 24 * 3600,
        "stages": [
            ("remind", 1.0, {"type": "print",
                             "message": "Legacy heartbeat overdue."}),
            ("release", 2.0, {"type": "file", "path": "legacy_release.txt",
                              "message": "Release the digital legacy."}),
        ],
    },
}


def list_templates() -> List[str]:
    """The names of all templates, sorted."""
    return sorted(TEMPLATES)


def get_template(name: str) -> Dict:
    """Fetch one template by name.

    Raises:
        TemplateError: If the name is unknown.
    """
    if name not in TEMPLATES:
        raise TemplateError(
            f"unknown template {name!r}; choose from {list_templates()}")
    return TEMPLATES[name]


def template_to_policy(template: Dict) -> EscalationPolicy:
    """Build the template's escalation policy, validating as we go.

    Stage thresholds are the base TTL scaled by each stage's multiplier.
    """
    ttl = template["ttl_seconds"]
    stages: List[Stage] = []
    for name, multiplier, payload in template["stages"]:
        stages.append(Stage(name, ttl * multiplier, payload))
    try:
        return EscalationPolicy(stages)
    except PolicyError as exc:
        raise TemplateError(f"template policy invalid: {exc}") from exc


def apply_template(name: str, overrides: Dict | None = None) -> Dict:
    """Produce a concrete config dict from a template.

    Returns a dict with ttl_seconds, grace_seconds, and payload (the final
    stage's payload), ready to feed the engine or save to a config file.
    Optional overrides replace top-level keys.

    Raises:
        TemplateError: If the template is unknown or malformed.
    """
    template = dict(get_template(name))
    # Validate the policy now so a broken preset fails fast.
    template_to_policy(template)
    config = {
        "template": name,
        "ttl_seconds": template["ttl_seconds"],
        "grace_seconds": template["grace_seconds"],
        "payload": template["stages"][-1][2],
    }
    if overrides:
        config.update(overrides)
    return config
