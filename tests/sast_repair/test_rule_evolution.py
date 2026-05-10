"""Tests for the offline rule-evolution proposal builder."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.rule_evolution import evolve_static_rules


def test_evolve_static_rules_default() -> None:
    result = evolve_static_rules()
    assert result["status"] == "no_candidate"
    assert result["delta_count"] == 0
    assert result["candidate"] is None
    gate = result["promotion_gate"]
    assert gate["min_fp_reduction_pp"] == 10
    assert gate["k"] == 5


def test_evolve_static_rules_with_inputs() -> None:
    result = evolve_static_rules(
        sarif_deltas=[
            {"rule_id": "r1", "classification": "false_positive"},
            {"rule_id": "r2", "classification": "true_positive"},
        ],
        ruleset="security-pack",
    )
    assert result["status"] == "candidate_generated"
    assert result["delta_count"] == 2
    assert result["ruleset"] == "security-pack"
    assert result["candidate"]["affected_rule_ids"] == ["r1", "r2"]
    assert result["evaluation"]["requires_offline_validation"] is True
