"""Reproduction test record and hard-evidence enforcement."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import (
    ReproductionTestRecord,
    TestExecResult,
)


def evaluate_hard_evidence(
    *,
    pre_fix_result: TestExecResult,
    post_fix_result: TestExecResult,
    fails_for_expected_reason: bool,
    flaky_flag: bool,
) -> bool:
    """Apply Phase 13 hard-evidence rules to a reproduction test."""
    if flaky_flag:
        return False
    if pre_fix_result is not TestExecResult.FAIL:
        return False
    if post_fix_result not in (TestExecResult.PASS, TestExecResult.FAIL):
        return False
    return bool(fails_for_expected_reason)


def build_reproduction_test_record(
    *,
    run_id: str,
    candidate_index: int,
    test_code: str = "",
    test_file: str | None = None,
    generation_method: str = "null-adapter",
    pre_fix_result: TestExecResult = TestExecResult.NOT_EXECUTED,
    post_fix_result: TestExecResult = TestExecResult.NOT_EXECUTED,
    fails_for_expected_reason: bool = False,
    flaky_flag: bool = False,
    flaky_entropy_score: float = 0.0,
    diagnostics: list[dict[str, object]] | None = None,
) -> ReproductionTestRecord:
    hard = evaluate_hard_evidence(
        pre_fix_result=pre_fix_result,
        post_fix_result=post_fix_result,
        fails_for_expected_reason=fails_for_expected_reason,
        flaky_flag=flaky_flag,
    )
    return ReproductionTestRecord(
        run_id=run_id,
        candidate_index=candidate_index,
        test_code=test_code,
        test_file=test_file,
        generation_method=generation_method,
        pre_fix_result=pre_fix_result,
        post_fix_result=post_fix_result,
        fails_for_expected_reason=fails_for_expected_reason,
        flaky_flag=flaky_flag,
        flaky_entropy_score=flaky_entropy_score,
        generated_test_is_hard_evidence=hard,
        diagnostics=list(diagnostics or []),
    )


__all__ = ["build_reproduction_test_record", "evaluate_hard_evidence"]
