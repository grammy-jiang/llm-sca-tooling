"""Lightweight structural maintainability oracle."""

from __future__ import annotations

import re

from llm_sca_tooling.evaluation.models import MaintainabilityOracleResult

__all__ = ["evaluate_diff"]


def evaluate_diff(
    *, oracle_run_id: str, diff_id: str, diff_text: str
) -> MaintainabilityOracleResult:
    files = _changed_files(diff_text)
    findings: list[str] = []
    locality = max(0.0, 1.0 - max(0, len(files) - 1) * 0.2)
    dependency_pass = (
        "import llm_sca_tooling.evaluation" not in diff_text
        or "src/llm_sca_tooling/evaluation" in diff_text
    )
    if not dependency_pass:
        findings.append("possible dependency direction violation")
    responsibility_pass = diff_text.count("def ") <= 10
    reuse_pass = "duplicate" not in diff_text.lower()
    side_effect_pass = "global " not in diff_text
    testability_pass = "time.sleep(" not in diff_text
    overall = all(
        [
            dependency_pass,
            responsibility_pass,
            reuse_pass,
            side_effect_pass,
            testability_pass,
        ]
    )
    return MaintainabilityOracleResult(
        oracle_run_id=oracle_run_id,
        diff_id=diff_id,
        change_locality_score=locality,
        dependency_direction_pass=dependency_pass,
        responsibility_pass=responsibility_pass,
        reuse_pass=reuse_pass,
        side_effect_pass=side_effect_pass,
        testability_pass=testability_pass,
        overall_pass=overall,
        findings=findings,
        diagnostics=[f"changed_files={len(files)}"],
    )


def _changed_files(diff_text: str) -> list[str]:
    return re.findall(r"^\+\+\+ b/(.+)$", diff_text, flags=re.MULTILINE)
