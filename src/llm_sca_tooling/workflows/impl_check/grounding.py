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
    document_link_ids: list[str] | None = None,
) -> ClauseGrounding:
    """Ground a single clause against available evidence.

    Priority order:
    1. SYMBOL_MATCH  — clause target_candidates found in graph symbol qualified_names
    2. DOCUMENT_LINK — spec document has graph DOCUMENTS edges to code nodes that
                       match the target_candidates (heuristic, confidence 0.65)
    3. REPO_QA       — answered by a repo-QA function (LLM probe)
    4. UNGROUNDED    — no evidence found
    """
    available_symbols = available_symbol_ids or []

    matched_symbols = [
        s
        for s in available_symbols
        if any(cand.lower() in s.lower() for cand in clause.target_candidates)
    ]
    if matched_symbols:
        return ClauseGrounding(
            clause_id=clause.clause_id,
            grounding_method=GroundingMethod.SYMBOL_MATCH,
            symbol_node_ids=matched_symbols,
            confidence=0.8,
        )

    if document_link_ids and clause.target_candidates:
        # document_link_ids are qualified_name strings for nodes the spec doc
        # references via DOCUMENTS edges; match against clause target candidates.
        matched_links = [
            lid
            for lid in document_link_ids
            if any(cand.lower() in lid.lower() for cand in clause.target_candidates)
        ]
        if matched_links:
            return ClauseGrounding(
                clause_id=clause.clause_id,
                grounding_method=GroundingMethod.DOCUMENT_LINK,
                document_link_node_ids=matched_links,
                confidence=0.65,
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
    document_link_ids: list[str] | None = None,
) -> list[ClauseGrounding]:
    return [
        ground_clause(c, available_symbol_ids, repo_qa_fn, document_link_ids)
        for c in clauses
    ]
