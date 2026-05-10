"""Tests for candidate patch generation."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.candidate_patch import (
    NullCandidatePatchGenerator,
    is_valid_unified_diff,
)
from llm_sca_tooling.workflows.bug_resolve.models import RepairContextRecord


def _ctx(suspects: list[str]) -> RepairContextRecord:
    return RepairContextRecord(
        run_id="r1",
        candidate_index=0,
        file_suspects=list(suspects),
    )


def test_null_generator_produces_valid_diff() -> None:
    g = NullCandidatePatchGenerator()
    cp = g.generate(_ctx(["src/example.py"]))
    assert cp.changed_files == ["src/example.py"]
    assert is_valid_unified_diff(cp.diff_text)


def test_null_generator_no_suspects() -> None:
    g = NullCandidatePatchGenerator()
    cp = g.generate(_ctx([]))
    assert cp.diff_text == ""
    assert cp.changed_files == []
    assert cp.confidence == 0.0


def test_is_valid_unified_diff_valid() -> None:
    diff = "--- a/x\n+++ b/x\n@@ -1,1 +1,1 @@\n-old\n+new\n"
    assert is_valid_unified_diff(diff) is True


def test_is_valid_unified_diff_empty() -> None:
    assert is_valid_unified_diff("") is False


def test_is_valid_unified_diff_missing_hunk() -> None:
    assert is_valid_unified_diff("--- a/x\n+++ b/x\nno hunk\n") is False


def test_is_valid_unified_diff_only_text() -> None:
    assert is_valid_unified_diff("just text") is False
