"""Offline rule-evolution stub."""

from __future__ import annotations

from typing import Any


def evolve_static_rules(
    *,
    sarif_deltas: list[dict[str, Any]] | None = None,
    ruleset: str | None = None,
) -> dict[str, Any]:
    """Phase 12 stub for the offline rule-evolution workflow.

    Returns a structured ``not_implemented_in_phase_12`` payload. The promotion
    gate is documented in the plan: ≥10 pp false-positive reduction at k=5
    with zero true-positive loss, reviewed candidate, separate offline workspace.
    """
    return {
        "status": "not_implemented_in_phase_12",
        "ruleset": ruleset,
        "delta_count": len(list(sarif_deltas or [])),
        "promotion_gate": {
            "min_fp_reduction_pp": 10,
            "k": 5,
            "tp_loss_tolerated": 0,
            "reviewable_candidate_required": True,
            "offline_workspace_required": True,
        },
    }


__all__ = ["evolve_static_rules"]
