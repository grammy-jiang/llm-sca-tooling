"""Graph-edge traversal shared by interface plugins."""

from __future__ import annotations

from llm_sca_tooling.plugins.base import TraversalLink
from llm_sca_tooling.plugins.capability import ConfidenceLevel, TraversalDirection
from llm_sca_tooling.schemas.enums import GraphEdgeType
from llm_sca_tooling.schemas.graph import GraphNode
from llm_sca_tooling.storage.graph_store import GraphStore

INTERFACE_EDGE_TYPES = {
    GraphEdgeType.EXPOSES,
    GraphEdgeType.CONSUMES,
    GraphEdgeType.IMPLEMENTS,
    GraphEdgeType.FFI,
}


def traverse_interface_edges(
    plugin_id: str, node_id: str, direction: TraversalDirection, graph_store: GraphStore
) -> list[TraversalLink]:
    node = graph_store.fetch_node(node_id)
    if node is None:
        return []
    outbound = direction in {TraversalDirection.OUTBOUND, TraversalDirection.BOTH}
    inbound = direction in {TraversalDirection.INBOUND, TraversalDirection.BOTH}
    links: list[TraversalLink] = []
    if outbound:
        rows = graph_store.conn.execute(
            "SELECT payload_json, target_id FROM graph_edges WHERE source_id=?",
            (node_id,),
        ).fetchall()
        links.extend(
            _links(
                plugin_id,
                node,
                rows,
                "target_id",
                TraversalDirection.OUTBOUND,
                graph_store,
            )
        )
    if inbound:
        rows = graph_store.conn.execute(
            "SELECT payload_json, source_id FROM graph_edges WHERE target_id=?",
            (node_id,),
        ).fetchall()
        links.extend(
            _links(
                plugin_id,
                node,
                rows,
                "source_id",
                TraversalDirection.INBOUND,
                graph_store,
            )
        )
    return links


def _links(
    plugin_id: str,
    source_node: GraphNode,
    rows,
    endpoint_key: str,
    direction: TraversalDirection,
    graph_store: GraphStore,
) -> list[TraversalLink]:
    links = []
    for row in rows:
        import json

        payload = json.loads(row["payload_json"])
        if payload.get("edge_type") not in {
            edge_type.value for edge_type in INTERFACE_EDGE_TYPES
        }:
            continue
        properties = payload.get("properties", {})
        if properties.get("plugin_id") != plugin_id:
            continue
        target = graph_store.fetch_node(row[endpoint_key])
        if target is None:
            continue
        confidence = ConfidenceLevel(properties.get("confidence") or "analyser")
        links.append(
            TraversalLink(
                from_node_id=source_node.node_id,
                to_node_id=target.node_id,
                via_interface_id=properties.get("interface_id", ""),
                plugin_id=plugin_id,
                edge_type=payload.get("edge_type", ""),
                confidence=confidence,
                operation_name=properties.get("operation_name"),
                direction=direction,
                from_repo_id=source_node.repo.repo_id,
                to_repo_id=target.repo.repo_id,
                from_language=(
                    source_node.properties.get("language")
                    if isinstance(source_node.properties.get("language"), str)
                    else None
                ),
                to_language=(
                    target.properties.get("language")
                    if isinstance(target.properties.get("language"), str)
                    else None
                ),
            )
        )
    return links
