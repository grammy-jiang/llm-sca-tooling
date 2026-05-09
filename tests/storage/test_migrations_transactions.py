from __future__ import annotations

import pytest

from llm_sca_tooling.schemas.enums import GraphNodeType
from llm_sca_tooling.storage import initialize_workspace
from llm_sca_tooling.storage.errors import GraphIntegrityError, MigrationError, WorkspaceIncompatibleError
from tests.storage.conftest import graph_edge, graph_node


def test_reopen_does_not_reapply_migration(tmp_path) -> None:
    first = initialize_workspace(tmp_path / "store")
    count = first.conn.execute("SELECT count(*) AS count FROM schema_migrations").fetchone()["count"]
    first.close()
    second = initialize_workspace(tmp_path / "store")
    assert second.conn.execute("SELECT count(*) AS count FROM schema_migrations").fetchone()["count"] == count
    second.close()


def test_migration_checksum_mismatch_fails(tmp_path) -> None:
    store = initialize_workspace(tmp_path / "store")
    store.conn.execute("UPDATE schema_migrations SET checksum='bad' WHERE version='0001'")
    store.conn.commit()
    store.close()
    with pytest.raises(MigrationError):
        initialize_workspace(tmp_path / "store")


def test_unknown_future_migration_fails(tmp_path) -> None:
    store = initialize_workspace(tmp_path / "store")
    store.conn.execute("INSERT INTO schema_migrations(version, applied_ts, checksum, description) VALUES ('9999', 'now', 'x', 'future')")
    store.conn.commit()
    store.close()
    with pytest.raises(WorkspaceIncompatibleError):
        initialize_workspace(tmp_path / "store")


def test_failed_graph_batch_leaves_no_partial_edge(workspace, repo_ref, snapshot, provenance) -> None:
    one = graph_node("node:one", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance)
    two = graph_node("node:two", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance)
    missing = graph_node("node:missing", GraphNodeType.FUNCTION, repo_ref, snapshot, provenance)
    workspace.graph.add_nodes([one, two])
    with pytest.raises(GraphIntegrityError):
        workspace.graph.add_edges([graph_edge("edge:ok", one, two, provenance), graph_edge("edge:bad", one, missing, provenance)])
    assert workspace.graph.count_edges(repo_ref.repo_id) == 0
