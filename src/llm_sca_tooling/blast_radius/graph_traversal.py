"""BFS graph traversal engine with confirmed/ambiguous split."""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from llm_sca_tooling.blast_radius.models import (
    AmbiguousLinkRecord,
    ImpactRecord,
    TraversalPolicy,
)

logger = logging.getLogger(__name__)

_ANALYSER_CONFIDENCE = 0.7


def build_nx_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> nx.DiGraph:
    """Build a NetworkX directed graph from node/edge dicts."""
    g: nx.DiGraph = nx.DiGraph()
    for node in nodes:
        nid = node.get("node_id") or node.get("id") or str(node)
        g.add_node(nid, **node)
    for edge in edges:
        src = edge.get("source") or edge.get("from")
        tgt = edge.get("target") or edge.get("to")
        if src and tgt:
            g.add_edge(src, tgt, **edge)
    return g


def traverse(
    graph: nx.DiGraph,
    changed_symbol_ids: list[str],
    policy: TraversalPolicy,
    *,
    analyser_threshold: float = _ANALYSER_CONFIDENCE,
) -> tuple[list[ImpactRecord], list[AmbiguousLinkRecord]]:
    """BFS traversal; split confirmed from ambiguous by edge confidence."""
    confirmed: list[ImpactRecord] = []
    ambiguous: list[AmbiguousLinkRecord] = []
    visited: set[str] = set(changed_symbol_ids)

    for start in changed_symbol_ids:
        if start not in graph:
            logger.debug("Changed symbol %s not in graph; skipping", start)
            continue
        _bfs_from(
            graph,
            start,
            policy,
            confirmed,
            ambiguous,
            visited,
            analyser_threshold,
        )

    return confirmed, ambiguous


def _bfs_from(
    graph: nx.DiGraph,
    start: str,
    policy: TraversalPolicy,
    confirmed: list[ImpactRecord],
    ambiguous: list[AmbiguousLinkRecord],
    visited: set[str],
    threshold: float,
) -> None:
    queue: list[tuple[str, int, list[str], list[str]]] = [(start, 0, [], [])]
    allowed = set(policy.follow_edge_types) if policy.follow_edge_types else None
    while queue:
        current, hop, path, edges_used = queue.pop(0)
        if hop >= policy.max_hops:
            continue
        for neighbor in graph.successors(current):
            if neighbor in visited:
                continue
            edge_data = graph.edges[current, neighbor]
            etype = edge_data.get("edge_type", edge_data.get("type", "calls"))
            confidence = float(edge_data.get("confidence", 0.5))
            new_path = path + [current]
            new_edges = edges_used + [etype]

            # Low-confidence edges always go to ambiguous (regardless of type)
            if confidence < threshold:
                ambiguous.append(
                    AmbiguousLinkRecord(
                        source_node_id=current,
                        target_node_id=neighbor,
                        edge_type=etype,
                        confidence=confidence,
                        match_method="candidate_edge",
                        reason_ambiguous=(
                            f"confidence {confidence:.2f} < threshold {threshold:.2f}"
                        ),
                        recommended_followup="confirm edge with deeper analysis",
                    )
                )
                continue

            # High-confidence edges: only follow if edge type is in policy
            if allowed and etype not in allowed:
                continue

            visited.add(neighbor)
            node_data = graph.nodes.get(neighbor, {})
            ntype = node_data.get("node_type", node_data.get("type", "symbol"))
            confirmed.append(
                ImpactRecord(
                    group=_infer_group(ntype, etype),
                    node_id=neighbor,
                    node_type=ntype,
                    path_from_changed_symbol=new_path,
                    hop_distance=hop + 1,
                    confidence="analyser" if confidence >= 0.9 else "heuristic",
                    confirmed=True,
                    edge_types_used=new_edges,
                )
            )
            queue.append((neighbor, hop + 1, new_path, new_edges))


def _infer_group(node_type: str, edge_type: str) -> Any:
    from llm_sca_tooling.blast_radius.models import ImpactGroup

    if node_type == "test" or "test" in node_type.lower():
        return ImpactGroup.tests
    if edge_type in {"exposes", "consumes", "ffi", "implements"}:
        return ImpactGroup.interfaces
    if node_type in {"document", "design_clause", "intent_node"}:
        return ImpactGroup.linked_docs_specs
    if "sarif" in node_type.lower() or edge_type == "warns_by":
        return ImpactGroup.sarif_reachability
    return ImpactGroup.direct_callers
