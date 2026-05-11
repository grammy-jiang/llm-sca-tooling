"""Reproduction test generation and hard-evidence rules."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import (
    CandidatePatch,
    ReproductionTestRecord,
)


def generate_reproduction_test(
    patch: CandidatePatch,
    *,
    pre_fix_result: str = "not_executed",
    post_fix_result: str = "not_executed",
    fails_for_expected_reason: bool = False,
    flaky_flag: bool = False,
) -> ReproductionTestRecord:
    primary = patch.changed_files[0] if patch.changed_files else "src/main.py"
    test_code = (
        f"def test_regression_{patch.candidate_index}():\n"
        f"    # assertflip: asserts the buggy behaviour\n"
        f"    from {primary.replace('/', '.').removesuffix('.py')} import target\n"
        f"    result = target(None)\n"
        f"    assert result is not None\n"
    )
    hard_evidence = (
        pre_fix_result == "fail"
        and fails_for_expected_reason
        and not flaky_flag
        and post_fix_result in {"pass", "fail"}
    )
    diagnostics: list[str] = []
    if pre_fix_result != "fail":
        diagnostics.append("pre_fix_did_not_fail: not_hard_evidence")
    return ReproductionTestRecord(
        run_id=patch.run_id,
        candidate_index=patch.candidate_index,
        test_code=test_code,
        test_file=f"tests/regression/test_patch_{patch.candidate_index}.py",
        generation_method="assertflip",
        pre_fix_result=pre_fix_result,
        post_fix_result=post_fix_result,
        fails_for_expected_reason=fails_for_expected_reason,
        flaky_flag=flaky_flag,
        generated_test_is_hard_evidence=hard_evidence,
        diagnostics=diagnostics,
    )
