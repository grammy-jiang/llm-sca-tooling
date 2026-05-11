"""Stage 4: Clause-to-code grounding."""

from __future__ import annotations

from llm_sca_tooling.impl_check.models import (
    Clause,
    ClauseGrounding,
    HarnessPolicyClause,
)


def ground_clause(clause: Clause | HarnessPolicyClause) -> ClauseGrounding:
    """Null-mode grounding: symbol match from target_candidates."""
    if clause.target_candidates:
        symbol_ids = [f"symbol:{t}" for t in clause.target_candidates]
        return ClauseGrounding(
            clause_id=clause.clause_id,
            grounding_method="symbol_match",
            symbol_node_ids=symbol_ids,
            file_node_ids=[
                f"file:{t.replace('.', '/')}.py" for t in clause.target_candidates
            ],
            confidence="heuristic",
        )
    return ClauseGrounding(
        clause_id=clause.clause_id,
        grounding_method="ungrounded",
        confidence="unknown",
        ungrounded_reason="no_target_candidates",
    )
