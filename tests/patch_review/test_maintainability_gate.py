"""Tests for maintainability_gate."""

from __future__ import annotations

from llm_sca_tooling.patch_review.maintainability_gate import run_maintainability_gate


def test_run_gate_returns_typed_result(safe_diff: str) -> None:
    result = run_maintainability_gate(safe_diff, diff_id="diff:test")
    assert result.diff_id
    assert isinstance(result.overall_pass, bool)
    assert isinstance(result.block_merge, bool)


def test_run_gate_handles_empty_diff() -> None:
    result = run_maintainability_gate("", diff_id="diff:empty")
    assert result.diff_id == "diff:empty"
