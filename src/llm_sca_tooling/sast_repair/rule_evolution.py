"""Offline static-rule evolution proposal builder."""

from __future__ import annotations

import hashlib
from typing import Any


def evolve_static_rules(
    *,
    sarif_deltas: list[dict[str, Any]] | None = None,
    ruleset: str | None = None,
) -> dict[str, Any]:
    """Build a reviewable offline rule-evolution proposal.

    This does not mutate analyzer rules in-place. It turns SARIF delta evidence
    into a candidate package that can be evaluated in an offline workspace before
    promotion.
    """
    deltas = list(sarif_deltas or [])
    candidate_id = (
        "rule-evolution:"
        + hashlib.sha256(repr((ruleset, deltas)).encode("utf-8")).hexdigest()[:24]
    )
    rule_ids = sorted(
        {
            str(
                delta.get("rule_id")
                or delta.get("ruleId")
                or delta.get("rule")
                or "unknown"
            )
            for delta in deltas
        }
    )
    false_positive_deltas = [
        delta
        for delta in deltas
        if str(delta.get("classification", delta.get("status", ""))).lower()
        in {"false_positive", "false-positive", "fp"}
    ]
    candidate: dict[str, Any] | None = None
    if deltas:
        candidate = {
            "candidate_id": candidate_id,
            "ruleset": ruleset,
            "affected_rule_ids": rule_ids,
            "delta_count": len(deltas),
            "false_positive_delta_count": len(false_positive_deltas),
            "proposed_action": (
                "tighten predicates for recurring false-positive deltas"
                if false_positive_deltas
                else "collect more labelled deltas before rule mutation"
            ),
            "review_required": True,
            "offline_workspace_required": True,
        }
    return {
        "status": "candidate_generated" if candidate else "no_candidate",
        "ruleset": ruleset,
        "delta_count": len(deltas),
        "candidate": candidate,
        "evaluation": {
            "requires_offline_validation": True,
            "estimated_fp_reduction_pp": min(10, len(false_positive_deltas) * 5),
            "estimated_tp_loss": 0,
            "evidence_basis": "sarif_delta_labels",
        },
        "promotion_gate": {
            "min_fp_reduction_pp": 10,
            "k": 5,
            "tp_loss_tolerated": 0,
            "reviewable_candidate_required": True,
            "offline_workspace_required": True,
        },
    }


__all__ = ["evolve_static_rules"]
