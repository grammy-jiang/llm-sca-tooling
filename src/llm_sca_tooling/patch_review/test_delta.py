"""Test-result delta builder."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.patch_review.models import (
    ConfidenceLevel,
    PocPlusResult,
    ReproductionTestResult,
    TestDeltaRecord,
)


def build_test_delta(
    diff_id: str,
    *,
    before: dict[str, str] | None = None,
    after: dict[str, str] | None = None,
    reproduction_test: str | None = None,
    poc_plus: str | None = None,
    flaky_rerun_entropy: float | None = None,
    flaky_tests: list[str] | None = None,
) -> TestDeltaRecord:
    """Compute newly failing/passing tests and reproduction status.

    ``before``/``after`` map ``test_id`` -> ``"passed"``/``"failed"``/``"skipped"``.
    Flaky tests are excluded from gate conclusions (they remain in the
    counts but never appear in ``newly_failing``/``newly_passing``).
    """
    before_map = before or {}
    after_map = after or {}
    flaky = set(flaky_tests or [])
    all_ids = set(before_map) | set(after_map)
    newly_failing: list[str] = []
    newly_passing: list[str] = []
    for tid in sorted(all_ids):
        if tid in flaky:
            continue
        b = before_map.get(tid, "unknown")
        a = after_map.get(tid, "unknown")
        if b == "passed" and a == "failed":
            newly_failing.append(tid)
        elif b == "failed" and a == "passed":
            newly_passing.append(tid)

    pb = sum(1 for v in before_map.values() if v == "passed")
    pa = sum(1 for v in after_map.values() if v == "passed")
    fb = sum(1 for v in before_map.values() if v == "failed")
    fa = sum(1 for v in after_map.values() if v == "failed")

    repro_value = (
        ReproductionTestResult(reproduction_test)
        if reproduction_test
        else ReproductionTestResult.NOT_AVAILABLE
    )
    poc_value = PocPlusResult(poc_plus) if poc_plus else PocPlusResult.NOT_AVAILABLE
    confidence = (
        ConfidenceLevel.UNKNOWN
        if not all_ids
        else ConfidenceLevel.HEURISTIC if flaky else ConfidenceLevel.ANALYSER
    )

    return TestDeltaRecord(
        diff_id=diff_id,
        tests_run=len(all_ids),
        tests_passed_before=pb,
        tests_passed_after=pa,
        tests_failed_before=fb,
        tests_failed_after=fa,
        newly_failing=newly_failing,
        newly_passing=newly_passing,
        reproduction_test_result=repro_value,
        poc_plus_result=poc_value,
        flaky_rerun_entropy=flaky_rerun_entropy,
        confidence=confidence,
    )


def reproduction_test_is_invalid(record: TestDeltaRecord) -> bool:
    """Generated reproduction tests that pass before AND after are invalid evidence."""
    return record.reproduction_test_result == ReproductionTestResult.EXECUTED_PASS_BOTH


def has_failing_required_test(
    record: TestDeltaRecord, required: list[str] | None = None
) -> bool:
    required_set = set(required or [])
    if not required_set:
        return bool(record.newly_failing)
    return any(t in required_set for t in record.newly_failing)


def _ensure_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise TypeError("expected mapping of test_id -> status")
    return {str(k): str(v) for k, v in value.items()}
