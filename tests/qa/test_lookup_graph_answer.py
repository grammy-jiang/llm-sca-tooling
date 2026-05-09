from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.qa.behaviour_trace import BehaviourTraceEngine
from llm_sca_tooling.qa.confidence import ConfidenceLabel
from llm_sca_tooling.qa.graph_query import GraphPathBuilder
from llm_sca_tooling.qa.lookup import FileLocLookup, SymbolLocLookup
from llm_sca_tooling.qa.question import QuestionClass, normalize_question
from llm_sca_tooling.qa.service import RepoQAService
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
from llm_sca_tooling.storage import initialize_workspace

TS = "2026-05-09T00:00:00Z"


def test_file_and_symbol_lookup_return_graph_citations(tmp_path: Path) -> None:
    workspace, repo_id = _workspace_with_graph(tmp_path)
    try:
        file_result = FileLocLookup(workspace.graph).lookup(
            normalize_question("Find the file `auth/views.py`"), [repo_id]
        )
        assert file_result.confidence == ConfidenceLabel.PARSER
        assert file_result.matched_nodes[0].file_path == "auth/views.py"

        symbol_result = SymbolLocLookup(workspace.graph).lookup(
            normalize_question("Which function handles `login_handler`?"), [repo_id]
        )
        assert symbol_result.confidence == ConfidenceLabel.PARSER
        assert symbol_result.matched_nodes[0].symbol_path == "auth.views.login_handler"
    finally:
        workspace.close()


def test_graph_path_document_link_and_behaviour_trace(tmp_path: Path) -> None:
    workspace, repo_id = _workspace_with_graph(tmp_path)
    try:
        builder = GraphPathBuilder(workspace.graph)
        paths = builder.build_path(
            "node:login", end_node_id="node:validate", edge_types=["calls"], max_depth=2
        )
        assert paths and paths[0].confidence == ConfidenceLabel.PARSER
        assert builder.find_document_links("node:login")

        trace = BehaviourTraceEngine(workspace.graph).trace(
            normalize_question("What happens when `login_handler` is called?"),
            [repo_id],
            max_hops=2,
        )
        assert trace.graph_paths
        assert trace.confidence == ConfidenceLabel.HEURISTIC
        assert trace.uncertainty
    finally:
        workspace.close()


def test_answer_repo_question_file_loc_and_unknown(tmp_path: Path) -> None:
    workspace, repo_id = _workspace_with_graph(tmp_path)
    try:
        answer = RepoQAService(workspace).answer(
            "Where is `login_handler` defined?", repos=[repo_id], synthesis=False
        )
        assert answer.question_class == QuestionClass.FILE_LOC
        assert answer.confidence == ConfidenceLabel.PARSER
        assert answer.evidence[0].file_path == "auth/views.py"

        synthesized = RepoQAService(workspace).answer(
            "Where is `login_handler` defined?", repos=[repo_id]
        )
        assert synthesized.synthesis_model == "null"
        assert "cited graph node" in synthesized.answer_text

        unknown = RepoQAService(workspace).answer(
            "Where is `MissingSymbol` defined?", repos=[repo_id], synthesis=False
        )
        assert unknown.confidence == ConfidenceLabel.UNKNOWN
        assert unknown.recommended_action
    finally:
        workspace.close()


def _workspace_with_graph(tmp_path: Path):
    workspace = initialize_workspace(tmp_path / "workspace")
    root = tmp_path / "repo"
    (root / "auth").mkdir(parents=True)
    (root / "auth" / "views.py").write_text(
        "def login_handler():\n    validate_user()\n\ndef validate_user():\n    return True\n",
        encoding="utf-8",
    )
    repo = workspace.repositories.register_repo(root, name="demo")
    repo_ref = RepoRef(
        repo_id=repo.repo_id, name=repo.name, default_branch=repo.default_branch
    )
    snapshot = SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="0123456789abcdef0123456789abcdef01234567",
        branch="main",
        dirty=False,
        index_status=IndexStatus.FRESH,
        captured_ts=TS,
    )
    provenance = Provenance(
        source_tool="test",
        source_version="0.1",
        source_run_id="run:test",
        source_event_id="event:test",
        repo=repo_ref,
        snapshot=snapshot,
        derivation=DerivationType.PARSER,
        confidence=1.0,
        evidence_strength=EvidenceStrength.HARD_STATIC,
        created_ts=TS,
        attributes={},
    )

    file_node = GraphNode(
        node_id="node:file:views",
        node_type=GraphNodeType.FILE,
        label="views.py",
        repo=repo_ref,
        snapshot=snapshot,
        file_path="auth/views.py",
        provenance=provenance,
        properties={},
        created_ts=TS,
    )
    login = GraphNode(
        node_id="node:login",
        node_type=GraphNodeType.FUNCTION,
        label="login_handler",
        qualified_name="auth.views.login_handler",
        repo=repo_ref,
        snapshot=snapshot,
        file_path="auth/views.py",
        span=SourceSpan(file_path="auth/views.py", start_line=1, end_line=2),
        provenance=provenance,
        properties={"local_name": "login_handler"},
        created_ts=TS,
    )
    validate = GraphNode(
        node_id="node:validate",
        node_type=GraphNodeType.FUNCTION,
        label="validate_user",
        qualified_name="auth.views.validate_user",
        repo=repo_ref,
        snapshot=snapshot,
        file_path="auth/views.py",
        span=SourceSpan(file_path="auth/views.py", start_line=4, end_line=5),
        provenance=provenance,
        properties={"local_name": "validate_user"},
        created_ts=TS,
    )
    doc = GraphNode(
        node_id="node:doc:auth",
        node_type=GraphNodeType.DESIGN_CLAUSE,
        label="Auth clause",
        repo=repo_ref,
        snapshot=snapshot,
        file_path="README.md",
        span=SourceSpan(file_path="README.md", start_line=1, end_line=1),
        provenance=provenance,
        properties={},
        created_ts=TS,
    )
    workspace.graph.add_nodes([file_node, login, validate, doc])
    workspace.graph.add_edges(
        [
            GraphEdge(
                edge_id="edge:contains:login",
                edge_type=GraphEdgeType.CONTAINS,
                source_id=file_node.node_id,
                target_id=login.node_id,
                repo=repo_ref,
                snapshot=snapshot,
                provenance=provenance,
                confidence=1.0,
                properties={},
                created_ts=TS,
            ),
            GraphEdge(
                edge_id="edge:calls",
                edge_type=GraphEdgeType.CALLS,
                source_id=login.node_id,
                target_id=validate.node_id,
                repo=repo_ref,
                snapshot=snapshot,
                provenance=provenance,
                confidence=1.0,
                properties={},
                created_ts=TS,
            ),
            GraphEdge(
                edge_id="edge:documents",
                edge_type=GraphEdgeType.DOCUMENTS,
                source_id=doc.node_id,
                target_id=login.node_id,
                repo=repo_ref,
                snapshot=snapshot,
                provenance=provenance,
                confidence=0.75,
                properties={},
                created_ts=TS,
            ),
        ]
    )
    return workspace, repo.repo_id
