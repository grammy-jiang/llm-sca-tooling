"""Stage 2: Intent graph construction (MIDS-VALVE)."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.workflows.impl_check.models import Clause, IntentGraph, IntentNode

_PROHIBITION_KEYWORDS = re.compile(
    r"\b(must not|shall not|must never|never|prohibited|forbidden|disallowed)\b",
    re.IGNORECASE,
)


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
    satisfies_edges: list[JsonObject] = []
    violates_edges: list[JsonObject] = []
    checks_edges: list[JsonObject] = []

    for clause in clauses:
        inode_id = f"inode:{clause.clause_id}"
        node = IntentNode(
            node_id=inode_id,
            clause_id=clause.clause_id,
            text_summary=clause.text[:120],
            target_symbol_ids=list(clause.target_candidates),
            evidence_node_ids=[],
            confidence=0.5 if clause.atomic else 0.3,
        )
        intent_nodes.append(node)

        if clause.parent_clause_id:
            parent_inode = f"inode:{clause.parent_clause_id}"
            decomposes_to_edges.append(
                {"from": parent_inode, "to": inode_id, "type": "decomposes_to"}
            )
            # Positive obligations satisfy the parent intent.
            if not _PROHIBITION_KEYWORDS.search(clause.text):
                satisfies_edges.append(
                    {"from": inode_id, "to": parent_inode, "type": "satisfies"}
                )

        # Prohibition clauses generate violates edges toward their targets.
        if _PROHIBITION_KEYWORDS.search(clause.text):
            for sym in clause.target_candidates:
                violates_edges.append(
                    {"from": inode_id, "to": f"sym:{sym}", "type": "violates"}
                )

        # Clauses that name specific symbols generate checks edges.
        for sym in clause.target_candidates:
            checks_edges.append(
                {"from": inode_id, "to": f"sym:{sym}", "type": "checks"}
            )

    return IntentGraph(
        graph_id=graph_id,
        doc_id=doc_id,
        clause_ids=[c.clause_id for c in clauses],
        intent_nodes=intent_nodes,
        decomposes_to_edges=decomposes_to_edges,
        satisfies_edges=satisfies_edges,
        violates_edges=violates_edges,
        checks_edges=checks_edges,
        snapshot_id=snapshot_id,
        created_ts=datetime.now(UTC).isoformat(),
    )
