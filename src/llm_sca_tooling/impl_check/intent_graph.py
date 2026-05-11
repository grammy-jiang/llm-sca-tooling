"""Stage 2: Intent graph construction."""

from __future__ import annotations

import uuid

from llm_sca_tooling.impl_check.models import (
    Clause,
    HarnessPolicyClause,
    IntentGraph,
    IntentNode,
)


def build_intent_graph(
    doc_id: str,
    clauses: list[Clause | HarnessPolicyClause],
    *,
    snapshot_id: str | None = None,
) -> IntentGraph:
    graph_id = f"intent:{doc_id}:{uuid.uuid4().hex[:8]}"
    nodes: list[IntentNode] = []
    decomposes: list[tuple[str, str]] = []
    for clause in clauses:
        symbols = [f"symbol:{t}" for t in clause.target_candidates]
        node = IntentNode(
            node_id=f"intent-node:{clause.clause_id}",
            clause_id=clause.clause_id,
            text_summary=clause.text[:80],
            target_symbol_ids=symbols,
            confidence="heuristic",
        )
        nodes.append(node)
        if isinstance(clause, Clause) and clause.parent_clause_id:
            decomposes.append((clause.parent_clause_id, clause.clause_id))
    return IntentGraph(
        graph_id=graph_id,
        doc_id=doc_id,
        clause_ids=[c.clause_id for c in clauses],
        intent_nodes=nodes,
        decomposes_to_edges=decomposes,
        snapshot_id=snapshot_id,
    )
