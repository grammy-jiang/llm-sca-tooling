"""Phase 15 linked docs/specs impact — flag stale design clauses."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType

if TYPE_CHECKING:
    from llm_sca_tooling.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)

_DOC_NODE_TYPES = {
    GraphNodeType.DOCUMENT,
    GraphNodeType.DESIGN_CLAUSE,
    GraphNodeType.INTENT_NODE,
}

_DOC_EDGE_TYPES = [
    GraphEdgeType.SATISFIES,
    GraphEdgeType.VIOLATES,
    GraphEdgeType.DOCUMENTS,
    GraphEdgeType.DECOMPOSES_TO,
]


def collect_linked_docs(
    changed_node_ids: list[str],
    graph_store: GraphStore,
    *,
    max_hops: int = 3,
) -> tuple[list[dict[str, object]], str]:
    """Collect design_clause / intent_node / document nodes linked to changed symbols.

    Returns (doc_node_dicts, summary_string).
    """
    docs: list[dict[str, object]] = []

    try:
        slice_ = graph_store.fetch_ego_graph(
            changed_node_ids,
            depth=max_hops,
            edge_types=_DOC_EDGE_TYPES,
        )
        for node in slice_.nodes:
            if node.node_id in set(changed_node_ids):
                continue
            if node.node_type in _DOC_NODE_TYPES:
                docs.append(
                    {
                        "node_id": node.node_id,
                        "node_type": node.node_type.value,
                        "label": node.label,
                        "potentially_stale": True,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Linked docs collection failed: %s", exc)

    summary = (
        f"{len(docs)} linked doc/spec node(s) may be stale after this change."
        if docs
        else "No linked docs/specs affected."
    )
    return docs, summary


__all__ = ["collect_linked_docs"]
