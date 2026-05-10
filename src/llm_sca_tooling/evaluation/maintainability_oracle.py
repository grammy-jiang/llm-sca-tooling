"""Lightweight structural maintainability oracle."""

from __future__ import annotations

import hashlib

from llm_sca_tooling.evaluation.benchmark_adapter import extract_changed_files
from llm_sca_tooling.evaluation.models import MaintainabilityOracleResult
from llm_sca_tooling.schemas.base import JsonObject


def evaluate_maintainability(
    diff_text: str, *, diff_id: str | None = None
) -> MaintainabilityOracleResult:
    touched_files = extract_changed_files(diff_text)
    file_count = len(touched_files)
    locality = max(0.0, 1.0 - max(0, file_count - 1) * 0.15)
    findings: list[JsonObject] = []
    dependency_pass = True
    touched_blob = "\n".join(touched_files)
    for line in diff_text.splitlines():
        if not line.startswith("+"):
            continue
        if "from llm_sca_tooling.fl" in line and "/evaluation/" in touched_blob:
            dependency_pass = False
            findings.append(
                {
                    "code": "evaluation_imports_fl",
                    "message": "evaluation code imports Phase 9 internals directly",
                }
            )
    responsibility_pass = file_count <= 5
    if not responsibility_pass:
        findings.append({"code": "wide_change", "file_count": file_count})
    reuse_pass = "class " not in diff_text or file_count <= 3
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
    digest = hashlib.sha256(diff_text.encode()).hexdigest()
    diff_hash = diff_id or f"diff:{digest[:24]}"
    return MaintainabilityOracleResult(
        oracle_run_id=f"oracle:{diff_hash.removeprefix('diff:')}",
        diff_id=diff_hash,
        change_locality_score=locality,
        dependency_direction_pass=dependency_pass,
        responsibility_pass=responsibility_pass,
        reuse_pass=reuse_pass,
        side_effect_pass=side_effect_pass,
        testability_pass=testability_pass,
        overall_pass=overall,
        findings=findings,
        diagnostics=[{"code": "phase10_rule_based_oracle"}],
    )
