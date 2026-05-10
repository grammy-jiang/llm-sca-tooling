"""Maintainability-gate wrapper around the Phase 10 oracle."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.evaluation.maintainability_oracle import evaluate_maintainability
from llm_sca_tooling.patch_review.models import MaintainabilityGateResult


def run_maintainability_gate(
    diff_text: str, *, diff_id: str | None = None
) -> MaintainabilityGateResult:
    """Run the Phase 10 oracle and convert the result into a gate decision.

    Block conditions:

    * ``dependency_direction_pass: False`` — patch introduces dependency
      inversion or layering violation.
    * Three or more individual properties failing simultaneously.
    """
    oracle = evaluate_maintainability(diff_text, diff_id=diff_id)
    properties = [
        oracle.dependency_direction_pass,
        oracle.responsibility_pass,
        oracle.reuse_pass,
        oracle.side_effect_pass,
        oracle.testability_pass,
    ]
    failed = sum(1 for prop in properties if not prop)
    block = (not oracle.dependency_direction_pass) or failed >= 3
    findings: list[dict[str, Any]] = list(oracle.findings)
    if block and oracle.dependency_direction_pass and failed >= 3:
        findings.append(
            {
                "code": "many_property_failures",
                "failed_count": failed,
                "block_reason": "three_or_more_properties_failed",
            }
        )
    return MaintainabilityGateResult(
        diff_id=oracle.diff_id,
        oracle_result_id=oracle.oracle_run_id,
        change_locality_pass=oracle.change_locality_score >= 0.5,
        dependency_direction_pass=oracle.dependency_direction_pass,
        responsibility_pass=oracle.responsibility_pass,
        reuse_pass=oracle.reuse_pass,
        side_effect_pass=oracle.side_effect_pass,
        testability_pass=oracle.testability_pass,
        overall_pass=oracle.overall_pass,
        findings=findings,
        block_merge=block,
    )
