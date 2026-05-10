"""Stage 2: Intent graph construction."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.workflows.impl_check.models import Clause, IntentGraph, IntentNode


def build_intent_graph(
    doc_id: str, clauses: list[Clause], snapshot_id: str | None = None
) -> IntentGraph:
    graph_id = (
        "igraph:"
        + hashlib.sha256(
            (doc_id + ":".join(c.clause_id for c in clauses)).encode()
        ).hexdigest()[:24]
    )

    intent_nodes: list[IntentNode] = []
    decomposes_to_edges: list[JsonObject] = []

    for clause in clauses:
        node = IntentNode(
            node_id=f"inode:{clause.clause_id}",
            clause_id=clause.clause_id,
            text_summary=clause.text[:120],
            target_symbol_ids=list(clause.target_candidates),
            evidence_node_ids=[],
            confidence=0.5 if clause.atomic else 0.3,
        )
        intent_nodes.append(node)

        if clause.parent_clause_id:
            decomposes_to_edges.append(
                {
                    "from": f"inode:{clause.parent_clause_id}",
                    "to": f"inode:{clause.clause_id}",
                    "type": "decomposes_to",
                }
            )

    return IntentGraph(
        graph_id=graph_id,
        doc_id=doc_id,
        clause_ids=[c.clause_id for c in clauses],
        intent_nodes=intent_nodes,
        decomposes_to_edges=decomposes_to_edges,
        satisfies_edges=[],
        violates_edges=[],
        checks_edges=[],
        snapshot_id=snapshot_id,
        created_ts=datetime.now(UTC).isoformat(),
    )
