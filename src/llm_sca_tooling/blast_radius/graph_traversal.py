"""Phase 15 BFS graph traversal engine with confirmed/ambiguous splitting."""

from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING

from llm_sca_tooling.blast_radius.models import (
    AmbiguousLinkRecord,
    ImpactGroup,
    ImpactRecord,
    MatchMethod,
)
from llm_sca_tooling.blast_radius.traversal_policy import TraversalPolicy
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType

if TYPE_CHECKING:
    from llm_sca_tooling.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)

# Edge types that indicate interface boundaries
_INTERFACE_BOUNDARY_TYPES = {
    GraphEdgeType.EXPOSES.value,
    GraphEdgeType.CONSUMES.value,
    GraphEdgeType.FFI.value,
    GraphEdgeType.IMPLEMENTS.value,
}

# Node types for services (beyond interface boundary)
_SERVICE_NODE_TYPES = {
    GraphNodeType.HTTP_ROUTE.value,
    GraphNodeType.WEBSOCKET_EVENT.value,
    GraphNodeType.GRPC_SERVICE.value,
    GraphNodeType.IDL_INTERFACE.value,
}

# Node types for tests
_TEST_NODE_TYPES = {
    GraphNodeType.TEST.value,
    GraphNodeType.GENERATED_TEST.value,
}

# Node types for SARIF
_SARIF_NODE_TYPES = {
    GraphNodeType.SARIF_ALERT.value,
    GraphNodeType.SAST_RULE.value,
}

# Node types for design/doc/spec
_DOC_NODE_TYPES = {
    GraphNodeType.DOCUMENT.value,
    GraphNodeType.DESIGN_CLAUSE.value,
    GraphNodeType.INTENT_NODE.value,
}


def _classify_group(
    node_type: str,
    edge_types_used: list[str],
    hop_distance: int,
    crossed_interface: bool,
    policy: TraversalPolicy,
) -> ImpactGroup:
    """Classify a reachable node into an ImpactGroup."""
    if node_type in _SARIF_NODE_TYPES:
        return ImpactGroup.SARIF_REACHABILITY
    if node_type in _DOC_NODE_TYPES:
        return ImpactGroup.LINKED_DOCS_SPECS
    if node_type in _TEST_NODE_TYPES:
        return ImpactGroup.TESTS
    if crossed_interface and policy.include_cross_repo:
        return ImpactGroup.REPOSITORIES
    if crossed_interface and node_type in _SERVICE_NODE_TYPES:
        return ImpactGroup.SERVICES
    if crossed_interface or any(
        et in _INTERFACE_BOUNDARY_TYPES for et in edge_types_used
    ):
        if node_type in _SERVICE_NODE_TYPES:
            return ImpactGroup.SERVICES
        return ImpactGroup.INTERFACES
    if hop_distance == 1:
        return ImpactGroup.DIRECT_CALLERS
    return ImpactGroup.DOWNSTREAM_BEHAVIOURS


def traverse_graph(
    changed_node_ids: list[str],
    graph_store: GraphStore,
    policy: TraversalPolicy,
    analyser_threshold: float = 0.75,
    hub_dampening_threshold: int = 100,
) -> tuple[list[ImpactRecord], list[AmbiguousLinkRecord]]:
    """BFS traversal from changed nodes with confirmed/ambiguous splitting.

    Returns (confirmed_impact_records, ambiguous_link_records).
    CPU-bound; callers should wrap in run_in_executor for async contexts.
    """
    confirmed: list[ImpactRecord] = []
    ambiguous: list[AmbiguousLinkRecord] = []

    allowed_edge_types = set(policy.follow_edge_types)
    start_set = set(changed_node_ids)

    # BFS state: (node_id, hop, path, edge_path, crossed_interface)
    visited: dict[str, int] = dict.fromkeys(start_set, 0)
    queue: deque[tuple[str, int, list[str], list[str], bool]] = deque()
    for nid in start_set:
        queue.append((nid, 0, [nid], [], False))

    while queue:
        node_id, hop, path, edge_path, crossed_iface = queue.popleft()
        if hop >= policy.max_hops:
            continue

        # Fetch ego graph one hop from this node
        from llm_sca_tooling.schemas.enums import GraphEdgeType  # noqa: PLC0415

        edge_type_filter = [
            GraphEdgeType(et)
            for et in allowed_edge_types
            if et in [e.value for e in GraphEdgeType]
        ]
        slice_ = graph_store.fetch_ego_graph(
            [node_id],
            depth=1,
            edge_types=edge_type_filter if edge_type_filter else None,
        )

        for edge in slice_.edges:
            # Determine direction
            if edge.source_id == node_id:
                neighbour_id = edge.target_id
            elif edge.target_id == node_id:
                neighbour_id = edge.source_id
            else:
                continue

            if neighbour_id in start_set:
                continue
            if edge.edge_type.value not in allowed_edge_types:
                continue

            next_hop = hop + 1
            if neighbour_id in visited and visited[neighbour_id] <= next_hop:
                continue

            # Hub dampening: skip overly connected nodes
            neighbour_node = graph_store.fetch_node(neighbour_id)
            if neighbour_node is None:
                continue

            # Stop at interface boundary for INTERNAL changes
            is_boundary_edge = edge.edge_type.value in _INTERFACE_BOUNDARY_TYPES
            next_crossed = crossed_iface or is_boundary_edge
            if policy.stop_at_interface_boundary and is_boundary_edge:
                # Report boundary node but don't traverse through it
                group = ImpactGroup.INTERFACES
                _add_to_confirmed_or_ambiguous(
                    neighbour_node.node_id,
                    neighbour_node.node_type.value,
                    path + [neighbour_id],
                    next_hop,
                    edge.confidence,
                    [edge.edge_type.value],
                    analyser_threshold,
                    confirmed,
                    ambiguous,
                    group=group,
                )
                continue

            if (
                not policy.include_test_nodes
                and neighbour_node.node_type.value in _TEST_NODE_TYPES
            ):
                continue
            if (
                not policy.include_sarif_reachability
                and neighbour_node.node_type.value in _SARIF_NODE_TYPES
            ):
                continue
            if (
                not policy.include_doc_spec_links
                and neighbour_node.node_type.value in _DOC_NODE_TYPES
            ):
                continue

            visited[neighbour_id] = next_hop
            next_path = path + [neighbour_id]
            next_edge_path = edge_path + [edge.edge_type.value]

            group = _classify_group(
                neighbour_node.node_type.value,
                next_edge_path,
                next_hop,
                next_crossed,
                policy,
            )

            _add_to_confirmed_or_ambiguous(
                neighbour_id,
                neighbour_node.node_type.value,
                next_path,
                next_hop,
                edge.confidence,
                next_edge_path,
                analyser_threshold,
                confirmed,
                ambiguous,
                group=group,
            )

            queue.append(
                (neighbour_id, next_hop, next_path, next_edge_path, next_crossed)
            )

    return confirmed, ambiguous


def _add_to_confirmed_or_ambiguous(
    node_id: str,
    node_type: str,
    path: list[str],
    hop: int,
    confidence: float,
    edge_types: list[str],
    threshold: float,
    confirmed: list[ImpactRecord],
    ambiguous: list[AmbiguousLinkRecord],
    group: ImpactGroup = ImpactGroup.DOWNSTREAM_BEHAVIOURS,
) -> None:
    is_confirmed = confidence >= threshold
    if is_confirmed:
        confirmed.append(
            ImpactRecord(
                group=group,
                node_id=node_id,
                node_type=node_type,
                path_from_changed_symbol=path,
                hop_distance=hop,
                confidence=confidence,
                confirmed=True,
                edge_types_used=edge_types,
            )
        )
    else:
        source_id = path[-2] if len(path) >= 2 else path[0]
        ambiguous.append(
            AmbiguousLinkRecord(
                source_node_id=source_id,
                target_node_id=node_id,
                edge_type=edge_types[-1] if edge_types else "unknown",
                confidence=confidence,
                match_method=MatchMethod.CANDIDATE_EDGE,
                reason_ambiguous=f"confidence {confidence:.2f} below analyser threshold {threshold:.2f}",
                recommended_followup="Run analyser-level pass to confirm or reject this link.",
            )
        )


__all__ = ["traverse_graph"]
