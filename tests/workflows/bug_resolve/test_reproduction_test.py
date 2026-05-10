"""Tests for reproduction test record + hard-evidence rule."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import TestExecResult
from llm_sca_tooling.workflows.bug_resolve.reproduction_test import (
    build_reproduction_test_record,
    evaluate_hard_evidence,
)


def test_hard_evidence_pass_after_fix() -> None:
    assert (
        evaluate_hard_evidence(
            pre_fix_result=TestExecResult.FAIL,
            post_fix_result=TestExecResult.PASS,
            fails_for_expected_reason=True,
            flaky_flag=False,
        )
        is True
    )


def test_hard_evidence_flaky() -> None:
    assert (
        evaluate_hard_evidence(
            pre_fix_result=TestExecResult.FAIL,
            post_fix_result=TestExecResult.PASS,
            fails_for_expected_reason=True,
            flaky_flag=True,
        )
        is False
    )


def test_hard_evidence_wrong_pre_fix() -> None:
    assert (
        evaluate_hard_evidence(
            pre_fix_result=TestExecResult.PASS,
            post_fix_result=TestExecResult.PASS,
            fails_for_expected_reason=True,
            flaky_flag=False,
        )
        is False
    )


def test_hard_evidence_wrong_post_fix() -> None:
    assert (
        evaluate_hard_evidence(
            pre_fix_result=TestExecResult.FAIL,
            post_fix_result=TestExecResult.NOT_EXECUTED,
            fails_for_expected_reason=True,
            flaky_flag=False,
        )
        is False
    )


def test_hard_evidence_no_expected_reason() -> None:
    assert (
        evaluate_hard_evidence(
            pre_fix_result=TestExecResult.FAIL,
            post_fix_result=TestExecResult.PASS,
            fails_for_expected_reason=False,
            flaky_flag=False,
        )
        is False
    )


def test_build_reproduction_test_record_default() -> None:
    rec = build_reproduction_test_record(run_id="r1", candidate_index=0)
    assert rec.generated_test_is_hard_evidence is False
    assert rec.pre_fix_result is TestExecResult.NOT_EXECUTED


def test_build_reproduction_test_record_assertflip() -> None:
    rec = build_reproduction_test_record(
        run_id="r1",
        candidate_index=0,
        pre_fix_result=TestExecResult.FAIL,
        post_fix_result=TestExecResult.PASS,
        fails_for_expected_reason=True,
    )
    assert rec.generated_test_is_hard_evidence is True
