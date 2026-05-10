"""Tests for test_delta."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import ConfidenceLevel, ReproductionTestResult
from llm_sca_tooling.patch_review.test_delta import (
    build_test_delta,
    has_failing_required_test,
    reproduction_test_is_invalid,
)


def test_newly_failing_and_passing() -> None:
    rec = build_test_delta(
        "d1",
        before={"t1": "passed", "t2": "failed"},
        after={"t1": "failed", "t2": "passed"},
    )
    assert rec.newly_failing == ["t1"]
    assert rec.newly_passing == ["t2"]
    assert rec.confidence == ConfidenceLevel.ANALYSER


def test_flaky_excluded() -> None:
    rec = build_test_delta(
        "d1",
        before={"t1": "passed"},
        after={"t1": "failed"},
        flaky_tests=["t1"],
    )
    assert rec.newly_failing == []
    assert rec.confidence == ConfidenceLevel.HEURISTIC


def test_unknown_confidence_when_empty() -> None:
    rec = build_test_delta("d1")
    assert rec.confidence == ConfidenceLevel.UNKNOWN


def test_reproduction_invalid_when_pass_both() -> None:
    rec = build_test_delta(
        "d1",
        before={"t": "passed"},
        after={"t": "passed"},
        reproduction_test="executed_pass_both",
    )
    assert reproduction_test_is_invalid(rec)


def test_has_failing_required_test_with_filter() -> None:
    rec = build_test_delta(
        "d1",
        before={"t1": "passed", "t2": "passed"},
        after={"t1": "failed", "t2": "failed"},
    )
    assert has_failing_required_test(rec, ["t1"]) is True
    assert has_failing_required_test(rec, ["other"]) is False
    assert has_failing_required_test(rec) is True


def test_reproduction_default_not_available() -> None:
    rec = build_test_delta("d1", before={"t": "passed"}, after={"t": "passed"})
    assert rec.reproduction_test_result == ReproductionTestResult.NOT_AVAILABLE
    assert not reproduction_test_is_invalid(rec)
