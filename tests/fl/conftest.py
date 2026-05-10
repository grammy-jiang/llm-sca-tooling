from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.schemas.enums import (
    DerivationType,
    EvidenceStrength,
    GraphEdgeType,
    GraphNodeType,
    IndexStatus,
)
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.schemas.provenance import (
    Provenance,
    RepoRef,
    SnapshotRef,
    SourceSpan,
)
from llm_sca_tooling.storage import WorkspaceStore, initialize_workspace
from llm_sca_tooling.storage.ids import snapshot_id_for

TS = "2026-05-09T00:00:00Z"
GIT_SHA = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture
def fl_workspace(tmp_path: Path) -> WorkspaceStore:
    store = initialize_workspace(tmp_path / ".llm-sca")
    yield store
    store.close()


@pytest.fixture
def fl_repo(tmp_path: Path, fl_workspace: WorkspaceStore):
    root = tmp_path / "repo"
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "pkg" / "core.py").write_text(
        "class UserService:\n"
        "    def validate(self, payload):\n"
        "        return payload['name'].lower()\n\n"
        "def caller(payload):\n"
        "    return UserService().validate(payload)\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_core.py").write_text(
        "from src.pkg.core import caller\n\n"
        "def test_caller():\n"
        "    assert caller({'name': 'Ada'}) == 'ada'\n",
        encoding="utf-8",
    )
    repo = fl_workspace.repositories.register_repo(root, name="demo")
    repo_ref = RepoRef(repo_id=repo.repo_id, name=repo.name)
    snapshot = SnapshotRef(
        repo_id=repo.repo_id,
        git_sha=GIT_SHA,
        branch="main",
        worktree_snapshot_id=None,
        dirty=False,
        index_status=IndexStatus.FRESH,
        captured_ts=TS,
    )
    provenance = Provenance(
        source_tool="test",
        source_version="0.1",
        repo=repo_ref,
        snapshot=snapshot,
        derivation=DerivationType.PARSER,
        confidence=1.0,
        evidence_strength=EvidenceStrength.HARD_STATIC,
        created_ts=TS,
    )
    nodes = [
        _node(
            "node:file:core",
            GraphNodeType.FILE,
            "src/pkg/core.py",
            repo_ref,
            snapshot,
            provenance,
            label="core.py",
        ),
        _node(
            "node:class:UserService",
            GraphNodeType.CLASS,
            "src/pkg/core.py",
            repo_ref,
            snapshot,
            provenance,
            label="UserService",
            qualified_name="pkg.core:UserService",
            start_line=1,
            end_line=3,
        ),
        _node(
            "node:method:validate",
            GraphNodeType.METHOD,
            "src/pkg/core.py",
            repo_ref,
            snapshot,
            provenance,
            label="validate",
            qualified_name="pkg.core:UserService.validate",
            start_line=2,
            end_line=3,
        ),
        _node(
            "node:function:caller",
            GraphNodeType.FUNCTION,
            "src/pkg/core.py",
            repo_ref,
            snapshot,
            provenance,
            label="caller",
            qualified_name="pkg.core:caller",
            start_line=5,
            end_line=6,
        ),
        _node(
            "node:test:core",
            GraphNodeType.TEST,
            "tests/test_core.py",
            repo_ref,
            snapshot,
            provenance,
            label="test_caller",
            qualified_name="tests.test_core:test_caller",
        ),
    ]
    fl_workspace.graph.add_nodes(nodes)
    fl_workspace.graph.add_edges(
        [
            GraphEdge(
                edge_id="edge:caller:validate",
                edge_type=GraphEdgeType.CALLS,
                source_id="node:function:caller",
                target_id="node:method:validate",
                repo=repo_ref,
                snapshot=snapshot,
                provenance=provenance,
                confidence=1.0,
                created_ts=TS,
            ),
            GraphEdge(
                edge_id="edge:test:validate",
                edge_type=GraphEdgeType.TESTS,
                source_id="node:test:core",
                target_id="node:method:validate",
                repo=repo_ref,
                snapshot=snapshot,
                provenance=provenance,
                confidence=1.0,
                created_ts=TS,
            ),
        ]
    )
    fl_workspace.repositories.set_latest_snapshot(
        repo.repo_id, snapshot_id_for(snapshot)
    )
    return repo


def _node(
    node_id: str,
    node_type: GraphNodeType,
    file_path: str,
    repo: RepoRef,
    snapshot: SnapshotRef,
    provenance: Provenance,
    *,
    label: str,
    qualified_name: str | None = None,
    start_line: int = 1,
    end_line: int = 10,
) -> GraphNode:
    return GraphNode(
        node_id=node_id,
        node_type=node_type,
        label=label,
        qualified_name=qualified_name,
        repo=repo,
        snapshot=snapshot,
        file_path=file_path,
        span=SourceSpan(file_path=file_path, start_line=start_line, end_line=end_line),
        provenance=provenance,
        properties={},
        created_ts=TS,
    )
