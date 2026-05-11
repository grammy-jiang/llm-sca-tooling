"""Maintainability gate wiring."""

from __future__ import annotations

from llm_sca_tooling.evaluation.maintainability_oracle import evaluate_diff
from llm_sca_tooling.patch_review.models import DiffRecord, MaintainabilityGateResult


def run_maintainability_gate(diff: DiffRecord) -> MaintainabilityGateResult:
    oracle = evaluate_diff(
        oracle_run_id=f"oracle:{diff.diff_id}",
        diff_id=diff.diff_id,
        diff_text=diff.diff_text,
    )
    failures = [
        not oracle.dependency_direction_pass,
        not oracle.responsibility_pass,
        not oracle.reuse_pass,
        not oracle.side_effect_pass,
        not oracle.testability_pass,
    ]
    block = not oracle.dependency_direction_pass or sum(failures) >= 3
    return MaintainabilityGateResult(
        diff_id=diff.diff_id,
        oracle_result_id=oracle.oracle_run_id,
        change_locality_pass=oracle.change_locality_score >= 0.4,
        dependency_direction_pass=oracle.dependency_direction_pass,
        responsibility_pass=oracle.responsibility_pass,
        reuse_pass=oracle.reuse_pass,
        side_effect_pass=oracle.side_effect_pass,
        testability_pass=oracle.testability_pass,
        overall_pass=oracle.overall_pass,
        findings=oracle.findings,
        block_merge=block,
    )
