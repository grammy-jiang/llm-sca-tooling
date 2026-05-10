"""Tests for dryrun."""

from __future__ import annotations

import pytest

from llm_sca_tooling.patch_review.diff_parser import parse_unified_diff
from llm_sca_tooling.patch_review.dryrun import (
    NullDryRUNGenerator,
    _ensure_str_list,
    degraded_confidence,
    detect_dryrun_mismatches,
)
from llm_sca_tooling.patch_review.models import (
    ConfidenceLevel,
    MismatchType,
)
from llm_sca_tooling.patch_review.test_delta import build_test_delta


def _diff(text: str):
    return parse_unified_diff(text)


def test_null_generator_predicts_changed_files(safe_diff: str) -> None:
    diff = _diff(safe_diff)
    pred = NullDryRUNGenerator().predict(
        diff, intended_behaviour_change="add None guard"
    )
    assert pred.expected_files_changed == diff.changed_files
    assert pred.intended_behaviour_change == "add None guard"


def test_extra_and_fewer_files_mismatches(safe_diff: str) -> None:
    diff = _diff(safe_diff)
    pred = NullDryRUNGenerator().predict(diff)
    mismatches = detect_dryrun_mismatches(pred, actual_files_changed=["unexpected.py"])
    types = {m.mismatch_type for m in mismatches}
    assert MismatchType.EXTRA_FILES_CHANGED in types
    assert MismatchType.FEWER_FILES_CHANGED in types


def test_unexpected_test_failure_and_pass(safe_diff: str) -> None:
    diff = _diff(safe_diff)
    pred = (
        NullDryRUNGenerator()
        .predict(diff)
        .model_copy(
            update={
                "expected_test_cases_passing": ["t1"],
                "expected_test_cases_failing": ["t2"],
            }
        )
    )
    test_delta = build_test_delta(
        diff.diff_id,
        before={"t1": "passed", "t2": "failed"},
        after={"t1": "failed", "t2": "passed"},
    )
    mismatches = detect_dryrun_mismatches(pred, test_delta=test_delta)
    types = {m.mismatch_type for m in mismatches}
    assert MismatchType.UNEXPECTED_TEST_FAILURE in types
    assert MismatchType.UNEXPECTED_TEST_PASS in types


def test_unexpected_side_effect_and_invariant_and_risk(safe_diff: str) -> None:
    diff = _diff(safe_diff)
    pred = (
        NullDryRUNGenerator()
        .predict(diff)
        .model_copy(update={"stated_risks": ["regress"]})
    )
    mismatches = detect_dryrun_mismatches(
        pred,
        actual_side_effects=["wrote_file"],
        invariants_violated=["sorted"],
        risks_materialised=["regress"],
    )
    types = {m.mismatch_type for m in mismatches}
    assert MismatchType.UNEXPECTED_SIDE_EFFECT in types
    assert MismatchType.INVARIANT_VIOLATED in types
    assert MismatchType.STATED_RISK_MATERIALISED in types


def test_degraded_confidence_levels(safe_diff: str) -> None:
    diff = _diff(safe_diff)
    pred = NullDryRUNGenerator().predict(diff)
    assert degraded_confidence([], ConfidenceLevel.ANALYSER) == ConfidenceLevel.ANALYSER

    inv_mismatches = detect_dryrun_mismatches(pred, invariants_violated=["x"])
    assert (
        degraded_confidence(inv_mismatches, ConfidenceLevel.ANALYSER)
        == ConfidenceLevel.UNKNOWN
    )

    other = detect_dryrun_mismatches(pred, actual_side_effects=["x"])
    assert (
        degraded_confidence(other, ConfidenceLevel.ANALYSER)
        == ConfidenceLevel.HEURISTIC
    )
    assert (
        degraded_confidence(other, ConfidenceLevel.HEURISTIC)
        == ConfidenceLevel.HEURISTIC
    )


def test_ensure_str_list_helpers() -> None:
    assert _ensure_str_list(None) == []
    assert _ensure_str_list([1, 2]) == ["1", "2"]
    with pytest.raises(TypeError):
        _ensure_str_list("nope")
