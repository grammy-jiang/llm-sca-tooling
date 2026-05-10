"""Tests for build_repair_context."""

from __future__ import annotations

import pytest

from llm_sca_tooling.workflows.bug_resolve.models import InvestigateResult
from llm_sca_tooling.workflows.bug_resolve.repair_context import (
    DEFAULT_TOP_FILES,
    EXPANDED_TOP_FILES,
    build_repair_context,
)


def _ir_with_candidates(n: int) -> InvestigateResult:
    return InvestigateResult(
        run_id="r1",
        issue_text_hash="h",
        ranked_candidates=[{"file_path": f"f{i}.py", "score": 0.5} for i in range(n)],
        top3_file_suspects=[f"f{i}.py" for i in range(min(3, n))],
    )


def test_returns_repair_context_record() -> None:
    ir = _ir_with_candidates(3)
    ctx = build_repair_context(
        run_id="r1", candidate_index=0, investigate_result=ir, context_budget=8000
    )
    assert ctx.run_id == "r1"
    assert ctx.candidate_index == 0
    assert len(ctx.file_suspects) <= DEFAULT_TOP_FILES


def test_caps_at_default_top_files() -> None:
    ir = _ir_with_candidates(20)
    ctx = build_repair_context(
        run_id="r1", candidate_index=0, investigate_result=ir, context_budget=80000
    )
    assert len(ctx.file_suspects) == DEFAULT_TOP_FILES


def test_expand_to_ten() -> None:
    ir = _ir_with_candidates(20)
    ctx = build_repair_context(
        run_id="r1",
        candidate_index=0,
        investigate_result=ir,
        context_budget=80000,
        expand_to_ten=True,
    )
    assert len(ctx.file_suspects) == EXPANDED_TOP_FILES


def test_zero_budget_raises() -> None:
    ir = _ir_with_candidates(3)
    with pytest.raises(ValueError):
        build_repair_context(
            run_id="r1",
            candidate_index=0,
            investigate_result=ir,
            context_budget=0,
        )


def test_budget_clamping() -> None:
    ir = _ir_with_candidates(20)
    ctx = build_repair_context(
        run_id="r1",
        candidate_index=0,
        investigate_result=ir,
        context_budget=100,
    )
    assert ctx.context_tokens_estimate <= 100
    assert ctx.budget_remaining == 100 - ctx.context_tokens_estimate
