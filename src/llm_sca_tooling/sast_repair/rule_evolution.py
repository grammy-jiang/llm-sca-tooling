"""Offline rule-evolution stub."""

from __future__ import annotations


def evolve_static_rules(*, ruleset: str, sarif_deltas: list[str]) -> dict[str, object]:
    return {
        "status": "not_implemented_in_phase_12",
        "ruleset": ruleset,
        "sarif_delta_count": len(sarif_deltas),
        "gate": "requires >=10pp FP reduction at k=5 with zero TP loss",
    }
