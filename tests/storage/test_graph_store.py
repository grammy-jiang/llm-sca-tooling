"""Tests for graph store writes and queries."""

from __future__ import annotations

import pytest

from llm_sca_tooling.schemas.graph import (
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
)
from llm_sca_tooling.schemas.provenance import SourceSpan
from llm_sca_tooling.storage.errors import GraphIntegrityError

NOW = "2026-05-09T12:00:00Z"


def _make_node(
    node_id,
    node_type,
    provenance,
    repo_ref,
    snapshot_ref,
    *,
    file_path=None,
    span=None,
):
    return GraphNode(
        node_id=node_id,
        node_type=node_type,
        label=node_id,
        repo=repo_ref,
        snapshot=snapshot_ref,
        provenance=provenance,
        created_ts=NOW,
        file_path=file_path,
        span=span,
    )


def _make_edge(edge_id, src, tgt, edge_type, provenance, repo_ref, snapshot_ref):
    return GraphEdge(
        edge_id=edge_id,
        edge_type=edge_type,
        source_id=src,
        target_id=tgt,
        repo=repo_ref,
        snapshot=snapshot_ref,
        provenance=provenance,
        created_ts=NOW,
    )


async def test_add_and_fetch_node(
    workspace, storage_provenance, storage_repo_ref, storage_snapshot_ref
) -> None:
    node = _make_node(
        "node:1",
        GraphNodeType.module,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    await workspace.graph.add_node(node)
    fetched = await workspace.queries.fetch_node("node:1")
    assert fetched is not None
    assert fetched.node_id == "node:1"


async def test_add_edge_requires_endpoints(
    workspace, storage_provenance, storage_repo_ref, storage_snapshot_ref
) -> None:
    edge = _make_edge(
        "edge:1",
        "node:missing",
        "node:also-missing",
        GraphEdgeType.imports,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    with pytest.raises(GraphIntegrityError):
        await workspace.graph.add_edge(edge)


async def test_add_edge_reports_missing_target(
    workspace, storage_provenance, storage_repo_ref, storage_snapshot_ref
) -> None:
    await workspace.graph.add_node(
        _make_node(
            "node:source",
            GraphNodeType.file,
            storage_provenance,
            storage_repo_ref,
            storage_snapshot_ref,
        )
    )
    edge = _make_edge(
        "edge:missing-target",
        "node:source",
        "node:missing",
        GraphEdgeType.imports,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    with pytest.raises(GraphIntegrityError, match="target node"):
        await workspace.graph.add_edge(edge)


async def test_add_edge_valid(
    workspace, storage_provenance, storage_repo_ref, storage_snapshot_ref
) -> None:
    n1 = _make_node(
        "node:A",
        GraphNodeType.file,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    n2 = _make_node(
        "node:B",
        GraphNodeType.module,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    await workspace.graph.add_nodes([n1, n2])
    edge = _make_edge(
        "edge:AB",
        "node:A",
        "node:B",
        GraphEdgeType.imports,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    await workspace.graph.add_edge(edge)
    fetched = await workspace.queries.fetch_edge("edge:AB")
    assert fetched is not None


async def test_duplicate_node_and_edge_are_idempotent(
    workspace, storage_provenance, storage_repo_ref, storage_snapshot_ref
) -> None:
    n1 = _make_node(
        "node:dup-a",
        GraphNodeType.file,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    n2 = _make_node(
        "node:dup-b",
        GraphNodeType.module,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    await workspace.graph.add_nodes([n1, n2])
    assert await workspace.graph.add_node(n1) == n1
    result = await workspace.graph.add_nodes([n1, n2])
    assert result.skipped == 2

    edge = _make_edge(
        "edge:dup",
        "node:dup-a",
        "node:dup-b",
        GraphEdgeType.imports,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    await workspace.graph.add_edge(edge)
    assert await workspace.graph.add_edge(edge) == edge
    edge_result = await workspace.graph.add_edges([edge])
    assert edge_result.skipped == 1


async def test_batch_add_nodes(
    workspace, storage_provenance, storage_repo_ref, storage_snapshot_ref
) -> None:
    nodes = [
        _make_node(
            f"node:{i}",
            GraphNodeType.function,
            storage_provenance,
            storage_repo_ref,
            storage_snapshot_ref,
        )
        for i in range(5)
    ]
    result = await workspace.graph.add_nodes(nodes)
    assert result.written == 5


async def test_fetch_nodes_by_type(
    workspace,
    storage_provenance,
    storage_repo_ref,
    storage_snapshot_ref,
    registered_repo,
) -> None:
    await workspace.graph.add_nodes(
        [
            _make_node(
                "node:fn1",
                GraphNodeType.function,
                storage_provenance,
                storage_repo_ref,
                storage_snapshot_ref,
            ),
            _make_node(
                "node:fn2",
                GraphNodeType.function,
                storage_provenance,
                storage_repo_ref,
                storage_snapshot_ref,
            ),
            _make_node(
                "node:cls1",
                GraphNodeType.class_,
                storage_provenance,
                storage_repo_ref,
                storage_snapshot_ref,
            ),
        ]
    )
    fns = await workspace.queries.fetch_nodes_by_type(
        registered_repo.repo_id, "function"
    )
    assert len(fns) == 2


async def test_batch_edge_insert_rolls_back_on_invalid(
    workspace, storage_provenance, storage_repo_ref, storage_snapshot_ref
) -> None:
    await workspace.graph.add_node(
        _make_node(
            "node:X",
            GraphNodeType.file,
            storage_provenance,
            storage_repo_ref,
            storage_snapshot_ref,
        )
    )
    invalid_edges = [
        _make_edge(
            "edge:e1",
            "node:MISSING",
            "node:X",
            GraphEdgeType.imports,
            storage_provenance,
            storage_repo_ref,
            storage_snapshot_ref,
        ),
    ]
    with pytest.raises(GraphIntegrityError):
        await workspace.graph.add_edges(invalid_edges)


async def test_count_nodes_and_edges(
    workspace,
    storage_provenance,
    storage_repo_ref,
    storage_snapshot_ref,
    registered_repo,
) -> None:
    await workspace.graph.add_nodes(
        [
            _make_node(
                "node:c1",
                GraphNodeType.class_,
                storage_provenance,
                storage_repo_ref,
                storage_snapshot_ref,
            ),
            _make_node(
                "node:c2",
                GraphNodeType.class_,
                storage_provenance,
                storage_repo_ref,
                storage_snapshot_ref,
            ),
        ]
    )
    count = await workspace.queries.count_nodes(registered_repo.repo_id)
    assert count == 2


async def test_graph_query_primitives_cover_filters_and_slices(
    workspace,
    storage_provenance,
    storage_repo_ref,
    storage_snapshot_ref,
    registered_repo,
) -> None:
    n_file = _make_node(
        "node:q-file",
        GraphNodeType.file,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
        file_path="pkg/app.py",
        span=SourceSpan(file_path="pkg/app.py", start_line=1, end_line=100),
    )
    n_func = _make_node(
        "node:q-func",
        GraphNodeType.function,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
        file_path="pkg/app.py",
        span=SourceSpan(file_path="pkg/app.py", start_line=10, end_line=20),
    )
    n_test = _make_node(
        "node:q-test",
        GraphNodeType.test,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
        file_path="tests/test_app.py",
        span=SourceSpan(file_path="tests/test_app.py", start_line=5, end_line=15),
    )
    await workspace.graph.add_nodes([n_file, n_func, n_test])
    contains = _make_edge(
        "edge:q-contains",
        "node:q-file",
        "node:q-func",
        GraphEdgeType.contains,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    tests = _make_edge(
        "edge:q-tests",
        "node:q-test",
        "node:q-func",
        GraphEdgeType.tests,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    await workspace.graph.add_edges([contains, tests])

    edges = await workspace.queries.fetch_edges_by_type(
        registered_repo.repo_id, "contains", snapshot_id="abc123deadbeef"
    )
    assert [e.edge_id for e in edges] == ["edge:q-contains"]

    by_file = await workspace.queries.fetch_by_file(
        registered_repo.repo_id, "pkg/app.py", limit=1
    )
    assert by_file.truncated is True
    assert by_file.snapshot_consistency == "clean"

    by_span = await workspace.queries.fetch_by_span(
        registered_repo.repo_id, "pkg/app.py", 1, 50
    )
    assert {node.node_id for node in by_span.nodes} == {"node:q-func"}

    outgoing = await workspace.queries.fetch_neighbours("node:q-file", direction="out")
    assert [node.node_id for node in outgoing.nodes] == ["node:q-func"]
    incoming = await workspace.queries.fetch_neighbours(
        "node:q-func", direction="in", edge_types=["tests"]
    )
    assert [node.node_id for node in incoming.nodes] == ["node:q-test"]
    missing = await workspace.queries.fetch_neighbours("node:missing")
    assert missing.snapshot_consistency == "unknown"

    ego = await workspace.queries.fetch_ego_graph(
        ["node:q-func"],
        depth=1,
        edge_types=["contains"],
        node_types=["file", "function"],
    )
    assert {node.node_id for node in ego.nodes} == {"node:q-file", "node:q-func"}
    assert await workspace.queries.count_edges(registered_repo.repo_id) == 2


async def test_ego_graph_empty_missing_and_truncated(
    workspace,
    storage_provenance,
    storage_repo_ref,
    storage_snapshot_ref,
) -> None:
    empty = await workspace.queries.fetch_ego_graph([])
    assert empty.provenance_summary == "empty input"

    missing = await workspace.queries.fetch_ego_graph(["node:missing"])
    assert missing.diagnostics

    nodes = [
        _make_node(
            f"node:ego-{i}",
            GraphNodeType.function,
            storage_provenance,
            storage_repo_ref,
            storage_snapshot_ref,
        )
        for i in range(3)
    ]
    await workspace.graph.add_nodes(nodes)
    await workspace.graph.add_edges(
        [
            _make_edge(
                "edge:ego-1",
                "node:ego-0",
                "node:ego-1",
                GraphEdgeType.calls,
                storage_provenance,
                storage_repo_ref,
                storage_snapshot_ref,
            ),
            _make_edge(
                "edge:ego-2",
                "node:ego-1",
                "node:ego-2",
                GraphEdgeType.calls,
                storage_provenance,
                storage_repo_ref,
                storage_snapshot_ref,
            ),
        ]
    )
    limited = await workspace.queries.fetch_ego_graph(["node:ego-1"], limit=1)
    assert limited.truncated is True


async def test_delete_nodes_and_edges_for_snapshot(
    workspace,
    storage_provenance,
    storage_repo_ref,
    storage_snapshot_ref,
    registered_repo,
) -> None:
    n1 = _make_node(
        "node:delete-a",
        GraphNodeType.file,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    n2 = _make_node(
        "node:delete-b",
        GraphNodeType.module,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    await workspace.graph.add_nodes([n1, n2])
    await workspace.graph.add_edge(
        _make_edge(
            "edge:delete",
            "node:delete-a",
            "node:delete-b",
            GraphEdgeType.imports,
            storage_provenance,
            storage_repo_ref,
            storage_snapshot_ref,
        )
    )

    edge_result = await workspace.graph.delete_edges_for_snapshot(
        registered_repo.repo_id, "abc123deadbeef", edge_types=["imports"]
    )
    node_result = await workspace.graph.delete_nodes_for_snapshot(
        registered_repo.repo_id, "abc123deadbeef", node_types=["file"]
    )
    assert edge_result.deleted == 1
    assert node_result.deleted == 1


async def test_upsert_node_and_edge_update_payload(
    workspace,
    storage_provenance,
    storage_repo_ref,
    storage_snapshot_ref,
) -> None:
    original = _make_node(
        "node:upsert-a",
        GraphNodeType.file,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    target = _make_node(
        "node:upsert-b",
        GraphNodeType.module,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    await workspace.graph.add_nodes([original, target])

    updated = GraphNode(
        node_id=original.node_id,
        node_type=GraphNodeType.file,
        label="updated.py",
        repo=storage_repo_ref,
        snapshot=storage_snapshot_ref,
        provenance=storage_provenance,
        created_ts=NOW,
        file_path="updated.py",
    )
    await workspace.graph.upsert_node(updated)
    fetched = await workspace.queries.fetch_node(original.node_id)
    assert fetched is not None
    assert fetched.label == "updated.py"

    edge = _make_edge(
        "edge:upsert",
        "node:upsert-a",
        "node:upsert-b",
        GraphEdgeType.imports,
        storage_provenance,
        storage_repo_ref,
        storage_snapshot_ref,
    )
    await workspace.graph.upsert_edge(edge)
    assert await workspace.queries.fetch_edge("edge:upsert") == edge
