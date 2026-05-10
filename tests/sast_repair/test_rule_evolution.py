"""Tests for the rule-evolution stub."""

from __future__ import annotations

from llm_sca_tooling.sast_repair.rule_evolution import evolve_static_rules


def test_evolve_static_rules_default() -> None:
    result = evolve_static_rules()
    assert result["status"] == "not_implemented_in_phase_12"
    assert result["delta_count"] == 0
    gate = result["promotion_gate"]
    assert gate["min_fp_reduction_pp"] == 10
    assert gate["k"] == 5


def test_evolve_static_rules_with_inputs() -> None:
    result = evolve_static_rules(
        sarif_deltas=[{"a": 1}, {"b": 2}], ruleset="security-pack"
    )
    assert result["delta_count"] == 2
    assert result["ruleset"] == "security-pack"
