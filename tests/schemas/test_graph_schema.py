from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_sca_tooling.schemas.base import canonical_json
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType, IndexStatus
from llm_sca_tooling.schemas.graph import (
    GraphDocument,
    GraphEdge,
    GraphNode,
    graph_has_mixed_snapshots,
)
from llm_sca_tooling.schemas.provenance import Provenance, RepoRef, SnapshotRef

TS = "2026-05-09T00:00:00Z"


def node(
    node_id: str,
    node_type: GraphNodeType,
    repo: RepoRef,
    snapshot: SnapshotRef,
    provenance: Provenance,
) -> GraphNode:
    return GraphNode(
        node_id=node_id,
        node_type=node_type,
        label=node_id,
        qualified_name=(
            node_id
            if node_type in {GraphNodeType.FUNCTION, GraphNodeType.METHOD}
            else None
        ),
        repo=repo,
        snapshot=snapshot,
        provenance=provenance,
        properties={},
        created_ts=TS,
    )


def edge(
    edge_id: str,
    edge_type: GraphEdgeType,
    source_id: str,
    target_id: str,
    repo: RepoRef,
    snapshot: SnapshotRef,
    provenance: Provenance,
) -> GraphEdge:
    return GraphEdge(
        edge_id=edge_id,
        edge_type=edge_type,
        source_id=source_id,
        target_id=target_id,
        repo=repo,
        snapshot=snapshot,
        provenance=provenance,
        confidence=1.0,
        created_ts=TS,
    )


def test_graph_document_round_trips(
    repo: RepoRef, snapshot: SnapshotRef, provenance: Provenance
) -> None:
    source = node("node:f1", GraphNodeType.FUNCTION, repo, snapshot, provenance)
    target = node("node:f2", GraphNodeType.FUNCTION, repo, snapshot, provenance)
    document = GraphDocument(
        graph_id="graph:demo",
        repo=repo,
        snapshot=snapshot,
        generated_by="test",
        generated_ts=TS,
        nodes=[source, target],
        edges=[
            edge(
                "edge:calls",
                GraphEdgeType.CALLS,
                source.node_id,
                target.node_id,
                repo,
                snapshot,
                provenance,
            )
        ],
    )
    assert (
        GraphDocument.model_validate_json(canonical_json(document)).graph_id
        == document.graph_id
    )


def test_missing_endpoint_fails(
    repo: RepoRef, snapshot: SnapshotRef, provenance: Provenance
) -> None:
    source = node("node:f1", GraphNodeType.FUNCTION, repo, snapshot, provenance)
    with pytest.raises(ValidationError):
        GraphDocument(
            graph_id="graph:demo",
            repo=repo,
            snapshot=snapshot,
            generated_by="test",
            generated_ts=TS,
            nodes=[source],
            edges=[
                edge(
                    "edge:bad",
                    GraphEdgeType.CALLS,
                    source.node_id,
                    "node:missing",
                    repo,
                    snapshot,
                    provenance,
                )
            ],
        )


def test_invalid_endpoint_pairing_fails(
    repo: RepoRef, snapshot: SnapshotRef, provenance: Provenance
) -> None:
    source = node("node:file", GraphNodeType.FILE, repo, snapshot, provenance)
    target = node("node:f2", GraphNodeType.FUNCTION, repo, snapshot, provenance)
    with pytest.raises(ValidationError):
        GraphDocument(
            graph_id="graph:demo",
            repo=repo,
            snapshot=snapshot,
            generated_by="test",
            generated_ts=TS,
            nodes=[source, target],
            edges=[
                edge(
                    "edge:bad",
                    GraphEdgeType.CALLS,
                    source.node_id,
                    target.node_id,
                    repo,
                    snapshot,
                    provenance,
                )
            ],
        )


def test_missing_provenance_fails(repo: RepoRef, snapshot: SnapshotRef) -> None:
    with pytest.raises(ValidationError):
        GraphNode(
            node_id="node:bad",
            node_type=GraphNodeType.FILE,
            label="bad",
            repo=repo,
            snapshot=snapshot,
            created_ts=TS,
        )


def test_invalid_enum_fails(
    repo: RepoRef, snapshot: SnapshotRef, provenance: Provenance
) -> None:
    with pytest.raises(ValidationError):
        GraphNode(
            node_id="node:bad",
            node_type="not-a-node",
            label="bad",
            repo=repo,
            snapshot=snapshot,
            provenance=provenance,
            created_ts=TS,
        )


def test_mixed_snapshot_detection(
    repo: RepoRef, snapshot: SnapshotRef, provenance: Provenance
) -> None:
    dirty = snapshot.model_copy(
        update={
            "git_sha": None,
            "dirty": True,
            "worktree_snapshot_id": "dirty:1",
            "index_status": IndexStatus.PARTIAL,
        }
    )
    source = node("node:f1", GraphNodeType.FUNCTION, repo, snapshot, provenance)
    target = node("node:f2", GraphNodeType.FUNCTION, repo, dirty, provenance)
    document = GraphDocument(
        graph_id="graph:demo",
        repo=repo,
        snapshot=snapshot,
        generated_by="test",
        generated_ts=TS,
        nodes=[source, target],
    )
    assert graph_has_mixed_snapshots(document)
