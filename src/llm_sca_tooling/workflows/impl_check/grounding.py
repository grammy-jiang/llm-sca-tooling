"""Stage 4: Clause-to-code grounding."""

from __future__ import annotations

from collections.abc import Callable

from llm_sca_tooling.workflows.impl_check.models import (
    Clause,
    ClauseGrounding,
    GroundingMethod,
)


def ground_clause(
    clause: Clause,
    available_symbol_ids: list[str] | None = None,
    repo_qa_fn: Callable[[Clause], list[str]] | None = None,
) -> ClauseGrounding:
    available_symbols = available_symbol_ids or []

    matched = [
        s
        for s in available_symbols
        if any(cand.lower() in s.lower() for cand in clause.target_candidates)
    ]
    if matched:
        return ClauseGrounding(
            clause_id=clause.clause_id,
            grounding_method=GroundingMethod.SYMBOL_MATCH,
            symbol_node_ids=matched,
            confidence=0.8,
        )

    if repo_qa_fn is not None and clause.target_candidates:
        refs = list(repo_qa_fn(clause)) or ["repo-qa:stub"]
        return ClauseGrounding(
            clause_id=clause.clause_id,
            grounding_method=GroundingMethod.REPO_QA,
            repo_qa_answer_refs=refs,
            confidence=0.7,
        )

    return ClauseGrounding(
        clause_id=clause.clause_id,
        grounding_method=GroundingMethod.UNGROUNDED,
        confidence=0.0,
        ungrounded_reason="no_symbol_match_and_no_repo_qa",
    )


def ground_clauses(
    clauses: list[Clause],
    available_symbol_ids: list[str] | None = None,
    repo_qa_fn: Callable[[Clause], list[str]] | None = None,
) -> list[ClauseGrounding]:
    return [ground_clause(c, available_symbol_ids, repo_qa_fn) for c in clauses]
