"""Tests for graph node, edge, and document models."""

from __future__ import annotations

import pytest

from llm_sca_tooling.schemas.base import canonical_dumps, canonical_loads
from llm_sca_tooling.schemas.graph import (
    GraphDocument,
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
    check_edge_endpoints,
)
from llm_sca_tooling.schemas.provenance import IndexStatus, SnapshotRef

NOW = "2026-05-09T12:00:00Z"
REPO_ID = "repo:demo"


def _make_node(
    node_id: str,
    node_type: GraphNodeType,
    parser_provenance,
    repo_ref,
    snapshot_ref,
) -> GraphNode:
    return GraphNode(
        node_id=node_id,
        node_type=node_type,
        label=node_id,
        repo=repo_ref,
        snapshot=snapshot_ref,
        provenance=parser_provenance,
        created_ts=NOW,
    )


def _make_edge(
    edge_id: str,
    edge_type: GraphEdgeType,
    source_id: str,
    target_id: str,
    parser_provenance,
    repo_ref,
    snapshot_ref,
) -> GraphEdge:
    return GraphEdge(
        edge_id=edge_id,
        edge_type=edge_type,
        source_id=source_id,
        target_id=target_id,
        repo=repo_ref,
        snapshot=snapshot_ref,
        provenance=parser_provenance,
        created_ts=NOW,
    )


def test_graph_node_round_trip(parser_provenance, repo_ref, snapshot_ref) -> None:
    node = _make_node(
        "node:1", GraphNodeType.module, parser_provenance, repo_ref, snapshot_ref
    )
    dumped = canonical_dumps(node)
    loaded = canonical_loads(dumped, GraphNode)
    assert loaded.node_id == node.node_id
    assert loaded.node_type == GraphNodeType.module


def test_graph_edge_self_loop_rejected(
    parser_provenance, repo_ref, snapshot_ref
) -> None:
    with pytest.raises(ValueError, match="must differ"):
        _make_edge(
            "e1",
            GraphEdgeType.calls,
            "node:1",
            "node:1",
            parser_provenance,
            repo_ref,
            snapshot_ref,
        )


def test_graph_edge_repo_id_mismatch_rejected(parser_provenance, repo_ref) -> None:

    mismatch_snap = SnapshotRef(repo_id="repo:DIFFERENT", captured_ts=NOW)
    with pytest.raises(ValueError, match="repo_id"):
        GraphEdge(
            edge_id="e1",
            edge_type=GraphEdgeType.imports,
            source_id="node:1",
            target_id="node:2",
            repo=repo_ref,  # repo_id = "repo:demo"
            snapshot=mismatch_snap,  # repo_id = "repo:DIFFERENT"
            provenance=parser_provenance,
            created_ts=NOW,
        )


def test_graph_document_valid(parser_provenance, repo_ref, snapshot_ref) -> None:
    node1 = _make_node(
        "node:1", GraphNodeType.module, parser_provenance, repo_ref, snapshot_ref
    )
    node2 = _make_node(
        "node:2", GraphNodeType.function, parser_provenance, repo_ref, snapshot_ref
    )
    edge = _make_edge(
        "e1",
        GraphEdgeType.contains,
        "node:1",
        "node:2",
        parser_provenance,
        repo_ref,
        snapshot_ref,
    )
    doc = GraphDocument(
        graph_id="g1",
        repo=repo_ref,
        snapshot=snapshot_ref,
        generated_by="test",
        generated_ts=NOW,
        nodes=[node1, node2],
        edges=[edge],
    )
    assert len(doc.nodes) == 2


def test_graph_document_mixed_snapshot_detection(
    parser_provenance, repo_ref, snapshot_ref
) -> None:

    other_snap = SnapshotRef(
        repo_id=REPO_ID,
        git_sha="deadbeef",
        captured_ts=NOW,
        index_status=IndexStatus.stale,
    )
    from llm_sca_tooling.schemas.provenance import (
        DerivationType,
        EvidenceStrength,
        Provenance,
    )

    other_prov = Provenance(
        source_tool="tool",
        repo=repo_ref,
        snapshot=other_snap,
        derivation=DerivationType.parser,
        confidence=1.0,
        evidence_strength=EvidenceStrength.hard_static,
        created_ts=NOW,
    )
    node1 = _make_node(
        "node:1", GraphNodeType.module, parser_provenance, repo_ref, snapshot_ref
    )
    node2 = GraphNode(
        node_id="node:2",
        node_type=GraphNodeType.function,
        label="fn",
        repo=repo_ref,
        snapshot=other_snap,
        provenance=other_prov,
        created_ts=NOW,
    )
    doc = GraphDocument(
        graph_id="g_mixed",
        repo=repo_ref,
        snapshot=snapshot_ref,
        generated_by="test",
        generated_ts=NOW,
        nodes=[node1, node2],
    )
    assert doc.has_mixed_snapshots() is True


def test_invalid_node_type_rejected() -> None:
    with pytest.raises(Exception):
        GraphNode.model_validate({"node_type": "NONEXISTENT_TYPE"})


def test_check_edge_endpoints_invalid_calls_source() -> None:
    err = check_edge_endpoints(
        GraphEdgeType.calls,
        GraphNodeType.module,  # invalid source for calls
        GraphNodeType.function,
    )
    assert err is not None


def test_check_edge_endpoints_valid_calls() -> None:
    err = check_edge_endpoints(
        GraphEdgeType.calls,
        GraphNodeType.function,
        GraphNodeType.method,
    )
    assert err is None
