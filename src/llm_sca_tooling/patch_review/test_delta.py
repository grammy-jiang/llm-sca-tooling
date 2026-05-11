"""Test-result delta model helpers."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import TestDeltaRecord


def compute_test_delta(
    *,
    diff_id: str,
    before_failed: list[str] | None = None,
    after_failed: list[str] | None = None,
    before_passed: list[str] | None = None,
    after_passed: list[str] | None = None,
    reproduction_test_result: str = "not_available",
    poc_plus_result: str = "not_available",
) -> TestDeltaRecord:
    before_failed = before_failed or []
    after_failed = after_failed or []
    before_passed = before_passed or []
    after_passed = after_passed or []
    return TestDeltaRecord(
        diff_id=diff_id,
        tests_run=len(set(before_failed + after_failed + before_passed + after_passed)),
        tests_passed_before=len(before_passed),
        tests_passed_after=len(after_passed),
        tests_failed_before=len(before_failed),
        tests_failed_after=len(after_failed),
        newly_failing=sorted(set(after_failed) - set(before_failed)),
        newly_passing=sorted(set(before_failed) - set(after_failed)),
        reproduction_test_result=reproduction_test_result,
        poc_plus_result=poc_plus_result,
    )
