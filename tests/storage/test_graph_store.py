from __future__ import annotations

import pytest

from llm_sca_tooling.schemas.enums import GraphNodeType, SnapshotConsistency
from llm_sca_tooling.storage.errors import GraphIntegrityError
from tests.storage.conftest import graph_edge, graph_node


def test_node_and_edge_insert_fetch(workspace, repo_ref, snapshot, provenance) -> None:
    one = graph_node("node:one", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance, file_path="src/app.py")
    two = graph_node("node:two", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance, file_path="src/app.py")
    workspace.graph.add_nodes([one, two])
    edge = graph_edge("edge:one-two", one, two, provenance)
    workspace.graph.add_edge(edge)
    assert workspace.graph.fetch_node(one.node_id).node_id == one.node_id
    assert workspace.graph.fetch_edge(edge.edge_id).edge_id == edge.edge_id
    assert workspace.graph.fetch_by_id(edge.edge_id).edge_id == edge.edge_id


def test_invalid_edge_endpoint_fails(workspace, repo_ref, snapshot, provenance) -> None:
    one = graph_node("node:one", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance)
    two = graph_node("node:two", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance)
    workspace.graph.add_node(one)
    with pytest.raises(GraphIntegrityError):
        workspace.graph.add_edge(graph_edge("edge:bad", one, two, provenance))


def test_batch_edge_insert_rolls_back(workspace, repo_ref, snapshot, provenance) -> None:
    one = graph_node("node:one", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance)
    two = graph_node("node:two", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance)
    missing = graph_node("node:missing", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance)
    workspace.graph.add_nodes([one, two])
    with pytest.raises(GraphIntegrityError):
        workspace.graph.add_edges([graph_edge("edge:ok", one, two, provenance), graph_edge("edge:bad", one, missing, provenance)])
    assert workspace.graph.fetch_edge("edge:ok") is None


def test_graph_queries_and_truncation(workspace, repo_ref, snapshot, provenance) -> None:
    one = graph_node("node:one", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance, file_path="src/app.py")
    two = graph_node("node:two", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance, file_path="src/app.py")
    workspace.graph.add_nodes([one, two])
    workspace.graph.add_edge(graph_edge("edge:one-two", one, two, provenance))
    assert workspace.graph.fetch_nodes_by_type(repo_ref.repo_id, GraphNodeType.FUNCTION)
    assert workspace.graph.fetch_by_file(repo_ref.repo_id, "src/app.py").nodes
    assert workspace.graph.fetch_by_span(repo_ref.repo_id, "src/app.py", 2, 3).nodes
    ego = workspace.graph.fetch_ego_graph([one.node_id], limit=1)
    assert ego.truncated
    assert workspace.graph.fetch_neighbours(one.node_id).edges


def test_mixed_snapshot_slice_reports_mixed(workspace, repo_ref, snapshot, dirty_snapshot, provenance) -> None:
    one = graph_node("node:one", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance, file_path="src/app.py")
    dirty_provenance = provenance.model_copy(update={"snapshot": dirty_snapshot})
    two = graph_node("node:two", GraphNodeType.FUNCTION, repo_ref, dirty_snapshot, dirty_provenance, file_path="src/app.py")
    workspace.graph.add_nodes([one, two])
    result = workspace.graph.fetch_by_file(repo_ref.repo_id, "src/app.py")
    assert result.snapshot_consistency == SnapshotConsistency.MIXED
