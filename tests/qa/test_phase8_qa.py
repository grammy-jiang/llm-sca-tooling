"""Phase 8 repository QA tests."""

from __future__ import annotations

import subprocess
from pathlib import Path
from shutil import which

import pytest

from llm_sca_tooling.mcp_server import MCPServer, McpServerConfig
from llm_sca_tooling.plugins.interface_record import (
    InterfaceKind,
    InterfaceOperation,
    InterfaceRecord,
    OperationType,
)
from llm_sca_tooling.plugins.store import InterfaceRecordStore
from llm_sca_tooling.plugins.traversal import CrossLanguageTraversalResult
from llm_sca_tooling.qa.answer import RepoAnswer, make_answer_id, recommended_action
from llm_sca_tooling.qa.behaviour_trace import trace_behaviour
from llm_sca_tooling.qa.blame import BlameResource
from llm_sca_tooling.qa.classifier import classify_question
from llm_sca_tooling.qa.confidence import derive_confidence
from llm_sca_tooling.qa.evidence_assembler import (
    AnswerEvidence,
    EvidenceAssembler,
    EvidenceType,
    bounded_snippet,
)
from llm_sca_tooling.qa.graph_query import GraphPath, GraphPathBuilder
from llm_sca_tooling.qa.interface_lookup import lookup_interface_contract
from llm_sca_tooling.qa.lookup import GraphNodeRef, lookup_files, lookup_symbols
from llm_sca_tooling.qa.question import QuestionClass, normalize_question
from llm_sca_tooling.qa.service import answer_repo_question
from llm_sca_tooling.qa.ship_gate import AnswerQualityGate, ShipGateConfig
from llm_sca_tooling.qa.synthesis import (
    NullSynthesisAdapter,
    SynthesisInput,
    SynthesisMode,
    evidence_summary,
)
from llm_sca_tooling.schemas.graph import (
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
)
from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    EvidenceStrength,
    IndexStatus,
    Provenance,
    RepoRef,
    SnapshotRef,
    SourceSpan,
)
from llm_sca_tooling.storage import WorkspaceStore

NOW = "2026-05-09T12:00:00Z"
GIT = which("git") or "git"


def _git(repo: Path, *args: str, capture_output: bool = False) -> None:
    subprocess.run(  # noqa: S603
        [GIT, *args],
        cwd=repo,
        check=True,
        capture_output=capture_output,
    )


@pytest.fixture()
async def workspace(tmp_path: Path) -> WorkspaceStore:
    return await WorkspaceStore.initialize(tmp_path / "workspace", in_memory=True)


@pytest.fixture()
async def registered_repo(workspace: WorkspaceStore, tmp_path: Path):
    root = tmp_path / "registered"
    root.mkdir()
    return await workspace.registry.register_repo(root, name="test")


@pytest.fixture()
def repo_ref(registered_repo) -> RepoRef:
    return RepoRef(repo_id=registered_repo.repo_id, name="test", default_branch="main")


@pytest.fixture()
async def snapshot_ref(workspace: WorkspaceStore, registered_repo) -> SnapshotRef:
    await workspace.snapshots.record_snapshot(
        registered_repo.repo_id,
        git_sha="abc123",
        branch="main",
        index_status="fresh",
    )
    return SnapshotRef(
        repo_id=registered_repo.repo_id,
        git_sha="abc123",
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )


@pytest.fixture()
def provenance(repo_ref: RepoRef, snapshot_ref: SnapshotRef) -> Provenance:
    return Provenance(
        source_tool="tree-sitter",
        repo=repo_ref,
        snapshot=snapshot_ref,
        derivation=DerivationType.parser,
        confidence=1.0,
        evidence_strength=EvidenceStrength.hard_static,
        created_ts=NOW,
    )


async def _seed_graph(
    workspace: WorkspaceStore,
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
    provenance: Provenance,
) -> None:
    module = GraphNode(
        node_id="node:module:app",
        node_type=GraphNodeType.module,
        label="app",
        repo=repo_ref,
        snapshot=snapshot_ref,
        provenance=provenance,
        created_ts=NOW,
        file_path="src/app.py",
    )
    main = GraphNode(
        node_id="node:function:main",
        node_type=GraphNodeType.function,
        label="main",
        qualified_name="app.main",
        repo=repo_ref,
        snapshot=snapshot_ref,
        provenance=provenance,
        created_ts=NOW,
        file_path="src/app.py",
        span=SourceSpan(file_path="src/app.py", start_line=1, end_line=2),
    )
    helper = GraphNode(
        node_id="node:function:helper",
        node_type=GraphNodeType.function,
        label="helper",
        qualified_name="app.helper",
        repo=repo_ref,
        snapshot=snapshot_ref,
        provenance=provenance,
        created_ts=NOW,
        file_path="src/app.py",
        span=SourceSpan(file_path="src/app.py", start_line=4, end_line=5),
    )
    document = GraphNode(
        node_id="node:doc:contract",
        node_type=GraphNodeType.design_clause,
        label="auth contract",
        repo=repo_ref,
        snapshot=snapshot_ref,
        provenance=provenance,
        created_ts=NOW,
        file_path="docs/spec.md",
    )
    await workspace.graph.add_nodes([module, main, helper, document])
    await workspace.graph.add_edges(
        [
            GraphEdge(
                edge_id="edge:calls",
                edge_type=GraphEdgeType.calls,
                source_id=main.node_id,
                target_id=helper.node_id,
                repo=repo_ref,
                snapshot=snapshot_ref,
                provenance=provenance,
                created_ts=NOW,
            ),
            GraphEdge(
                edge_id="edge:documents",
                edge_type=GraphEdgeType.documents,
                source_id=document.node_id,
                target_id=main.node_id,
                repo=repo_ref,
                snapshot=snapshot_ref,
                provenance=provenance,
                created_ts=NOW,
            ),
        ]
    )


def test_question_normalization_and_classifier() -> None:
    cases = {
        "Where is `src/app.py` implemented?": QuestionClass.file_loc,
        "Which function handles `app.main`?": QuestionClass.symbol_loc,
        "What happens when `app.main` calls `app.helper`?": QuestionClass.behaviour_trace,
        "Is the auth contract enforced?": QuestionClass.contract_check,
        "Summarize this project": QuestionClass.other,
    }
    for text, expected in cases.items():
        question = normalize_question(text)
        result = classify_question(question, use_llm_fallback=False)
        assert result.question_class == expected
        assert result.matched_rules or expected == QuestionClass.other
    ambiguous = classify_question(normalize_question("Where is the contract enforced?"))
    assert ambiguous.alternative_class is not None


async def test_file_and_symbol_lookup(
    workspace: WorkspaceStore,
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
    provenance: Provenance,
) -> None:
    await _seed_graph(workspace, repo_ref, snapshot_ref, provenance)
    file_result = await lookup_files(
        workspace, normalize_question("Where is src/app.py?")
    )
    symbol_result = await lookup_symbols(workspace, normalize_question("Find app.main"))
    empty = await lookup_symbols(workspace, normalize_question("Find MissingSymbol"))
    assert file_result.confidence == "parser"
    assert file_result.matched_nodes[0].file_path == "src/app.py"
    assert symbol_result.confidence == "parser"
    assert symbol_result.matched_nodes[0].node_id == "node:function:main"
    assert empty.confidence == "unknown"


async def test_graph_path_and_document_link(
    workspace: WorkspaceStore,
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
    provenance: Provenance,
) -> None:
    await _seed_graph(workspace, repo_ref, snapshot_ref, provenance)
    builder = GraphPathBuilder(workspace.queries)
    path = await builder.build_path("node:function:main", "node:function:helper")
    links = await builder.linked_documents(
        GraphNodeRef(
            node_id="node:function:main",
            node_type="function",
            repo_id=repo_ref.repo_id,
            source="test",
        )
    )
    assert path is not None
    assert path.edge_ids == ["edge:calls"]
    assert links[0].document_node_id == "node:doc:contract"


async def test_behaviour_trace_and_answer_service(
    workspace: WorkspaceStore,
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
    provenance: Provenance,
) -> None:
    await _seed_graph(workspace, repo_ref, snapshot_ref, provenance)
    trace = await trace_behaviour(
        workspace, normalize_question("What happens when `app.main` runs?")
    )
    no_start = await trace_behaviour(workspace, normalize_question("how does it flow"))
    missing = await trace_behaviour(workspace, normalize_question("What happens then?"))
    answer = await answer_repo_question(
        workspace,
        workspace.queries,
        question="What happens when `app.main` runs?",
        synthesis=False,
    )
    unknown = await answer_repo_question(
        workspace, workspace.queries, question="Find MissingSymbol", synthesis=False
    )
    assert trace.confidence == "heuristic"
    assert no_start.diagnostics == ["NO_START_SYMBOL"]
    assert missing.confidence == "unknown"
    assert answer.confidence == "heuristic"
    assert answer.uncertainty
    assert unknown.confidence == "unknown"
    assert unknown.recommended_action


async def test_service_symbol_contract_other_and_synthesis(
    workspace: WorkspaceStore,
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
    provenance: Provenance,
) -> None:
    await _seed_graph(workspace, repo_ref, snapshot_ref, provenance)
    store = InterfaceRecordStore(workspace)
    await store.store_records(
        [
            InterfaceRecord(
                interface_id="iface:http:contract",
                kind=InterfaceKind.http,
                plugin_id="http-rest",
                plugin_version="1.0",
                interface_name="GET /contract",
                source_repos=[repo_ref.repo_id],
                confidence="parser",
                snapshot_ids={repo_ref.repo_id: snapshot_ref.git_sha},
            )
        ]
    )
    symbol = await answer_repo_question(
        workspace,
        workspace.queries,
        question="Which function handles `app.main`?",
        synthesis=True,
    )
    contract = await answer_repo_question(
        workspace,
        workspace.queries,
        question="Is the contract enforced?",
        question_class_hint=QuestionClass.contract_check.value,
        interface_store=store,
        synthesis=False,
    )
    other = await answer_repo_question(
        workspace,
        workspace.queries,
        question="Summarize app",
        question_class_hint=QuestionClass.other.value,
        synthesis=False,
    )
    assert symbol.confidence == "parser"
    assert symbol.synthesis_model == "null"
    assert contract.evidence[0].evidence_type == EvidenceType.interface_contract
    assert other.confidence in {"analyser", "heuristic", "parser"}


async def test_behaviour_trace_cross_language_payload(
    workspace: WorkspaceStore,
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
    provenance: Provenance,
) -> None:
    await _seed_graph(workspace, repo_ref, snapshot_ref, provenance)

    class FakeTraverser:
        async def traverse(self, node_id: str, *, max_hops: int):
            return CrossLanguageTraversalResult(
                start_node_id=node_id,
                reached_node_ids=["node:function:helper"],
                total_hops=0,
                terminated_early=False,
            )

    result = await trace_behaviour(
        workspace,
        normalize_question("Trace cross-language HTTP `app.main`"),
        FakeTraverser(),  # type: ignore[arg-type]
    )
    assert result.traversal
    assert result.traversal["reached_node_ids"] == ["node:function:helper"]


async def test_interface_lookup(
    workspace: WorkspaceStore,
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
    provenance: Provenance,
) -> None:
    await _seed_graph(workspace, repo_ref, snapshot_ref, provenance)
    record = InterfaceRecord(
        interface_id="iface:http:test",
        kind=InterfaceKind.http,
        plugin_id="http-rest",
        plugin_version="1.0",
        interface_name="GET /v1/users",
        definition_files=["openapi.yaml"],
        source_repos=[repo_ref.repo_id],
        operations=[
            InterfaceOperation(
                operation_id="op:get-users",
                interface_id="iface:http:test",
                name="getUsers",
                operation_type=OperationType.route,
                server_handler_node_ids=["node:function:main"],
                client_callsite_node_ids=["node:function:helper"],
                confidence="parser",
            )
        ],
        confidence="parser",
        snapshot_ids={repo_ref.repo_id: snapshot_ref.git_sha},
    )
    store = InterfaceRecordStore(workspace)
    await store.store_records([record])
    found = await lookup_interface_contract(
        store,
        workspace.queries,
        plugin_id="http-rest",
        interface_name="GET /v1/users",
        include_operations=False,
    )
    assert found is not None
    assert found.matched_operations == []
    assert found.server_node_refs[0].node_id == "node:function:main"
    assert (
        await lookup_interface_contract(
            store, workspace.queries, plugin_id="http-rest", interface_name="missing"
        )
        is None
    )


def test_evidence_confidence_answer_and_synthesis() -> None:
    ev = AnswerEvidence(
        evidence_id="ev:1",
        evidence_type=EvidenceType.file_node,
        node_id="node:module:app",
        node_type="module",
        file_path="src/app.py",
        confidence="parser",
        source="exact_path",
    )
    assert bounded_snippet("\n".join(str(i) for i in range(10))).count("\n") == 4
    with pytest.raises(ValueError):
        AnswerEvidence(
            evidence_id="ev:long",
            evidence_type=EvidenceType.file_node,
            confidence="heuristic",
            source="test",
            content_snippet="\n".join(str(i) for i in range(6)),
        )
    assembler = EvidenceAssembler()
    assert assembler.from_graph_paths(
        [GraphPath(path_id="path:test", node_ids=["node:module:app"])]
    )
    confidence, reason, uncertainty = derive_confidence(QuestionClass.file_loc, [ev])
    assert (confidence, uncertainty) == ("parser", None)
    assert "exact_path" in reason
    assert derive_confidence(QuestionClass.behaviour_trace, [ev])[0] == "unknown"
    doc = ev.model_copy(update={"evidence_type": EvidenceType.document_link})
    sast = ev.model_copy(update={"evidence_type": EvidenceType.sast_alert})
    assert derive_confidence(QuestionClass.contract_check, [doc, sast])[0] == "analyser"
    assert derive_confidence(QuestionClass.file_loc, [ev], has_mixed_snapshot=True)[2]
    summary = evidence_summary([ev])
    output = NullSynthesisAdapter().synthesize(
        SynthesisInput(
            question_class=QuestionClass.file_loc,
            normalized_question="where is app",
            evidence_summary=summary,
            graph_nodes=[
                GraphNodeRef(
                    node_id="node:module:app",
                    node_type="module",
                    repo_id="repo:test",
                    source="test",
                )
            ],
            mode=SynthesisMode.technical_summary,
        )
    )
    answer = RepoAnswer(
        answer_id=make_answer_id("q:1", [ev]),
        question_id="q:1",
        question_class=QuestionClass.file_loc,
        answer_text=output.answer_text,
        confidence=confidence,
        confidence_reason=reason,
        evidence=[ev],
        graph_node_ids=["node:module:app"],
    )
    assert answer.synthesis_model is None
    with pytest.raises(ValueError):
        RepoAnswer(
            answer_id="a:bad",
            question_id="q:bad",
            question_class=QuestionClass.file_loc,
            answer_text="bad",
            confidence="parser",
            confidence_reason="bad",
            evidence=[],
            graph_node_ids=[],
        )
    with pytest.raises(ValueError):
        RepoAnswer(
            answer_id="a:no-node",
            question_id="q:no-node",
            question_class=QuestionClass.file_loc,
            answer_text="bad",
            confidence="parser",
            confidence_reason="bad",
            evidence=[ev],
            graph_node_ids=[],
        )
    with pytest.raises(ValueError):
        RepoAnswer(
            answer_id="a:no-action",
            question_id="q:no-action",
            question_class=QuestionClass.file_loc,
            answer_text="bad",
            confidence="unknown",
            confidence_reason="bad",
        )
    with pytest.raises(ValueError):
        RepoAnswer(
            answer_id="a:no-uncertainty",
            question_id="q:no-uncertainty",
            question_class=QuestionClass.behaviour_trace,
            answer_text="bad",
            confidence="heuristic",
            confidence_reason="bad",
            evidence=[ev],
            graph_node_ids=["node:module:app"],
        )
    unknown = RepoAnswer(
        answer_id="a:unknown",
        question_id="q:unknown",
        question_class=QuestionClass.file_loc,
        answer_text="none",
        confidence="unknown",
        confidence_reason="none",
        recommended_action=recommended_action(QuestionClass.file_loc),
    )
    assert unknown.recommended_action
    assert "Register" in recommended_action(QuestionClass.symbol_loc)
    assert "plugin_reload" in recommended_action(QuestionClass.contract_check)


def test_ship_gate_caps_confidence() -> None:
    path_ev = AnswerEvidence(
        evidence_id="ev:path",
        evidence_type=EvidenceType.graph_path,
        node_id="node:start",
        confidence="parser",
        source="graph_path",
    )
    answer = RepoAnswer(
        answer_id="a:trace",
        question_id="q:trace",
        question_class=QuestionClass.behaviour_trace,
        answer_text="trace",
        confidence="parser",
        confidence_reason="test",
        evidence=[path_ev],
        graph_node_ids=["node:start"],
        uncertainty="Evidence comes from mixed snapshots.",
    )
    gated = AnswerQualityGate().apply(answer, ShipGateConfig())
    assert gated.confidence == "heuristic"
    assert any(
        not r.passed for r in AnswerQualityGate().check(answer, ShipGateConfig())
    )


def test_blame_resource_line_filters(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", capture_output=True)
    _git(repo, "config", "user.name", "Tester")
    _git(repo, "config", "user.email", "tester@example.com")
    (repo / "app.py").write_text("one\ntwo\n")
    _git(repo, "add", "app.py", capture_output=True)
    _git(repo, "commit", "-m", "initial", capture_output=True)
    blame = BlameResource.from_git(repo, "repo:test", "app.py", line=2)
    ranged = BlameResource.from_git(
        repo, "repo:test", "app.py", start_line=1, end_line=1
    )
    assert len(blame.entries) == 1
    assert len(ranged.entries) == 1
    assert blame.entries[0].commit.author == "Tester"
    assert BlameResource.from_git(repo, "repo:test", "missing.py").diagnostics
    not_git = tmp_path / "not-git"
    not_git.mkdir()
    (not_git / "file.txt").write_text("x\n")
    assert BlameResource.from_git(not_git, "repo:test", "file.txt").diagnostics


async def test_mcp_phase8_tools(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", capture_output=True)
    _git(repo, "config", "user.name", "Tester")
    _git(repo, "config", "user.email", "tester@example.com")
    (repo / "app.py").write_text("def main():\n    return 1\n")
    _git(repo, "add", "app.py", capture_output=True)
    _git(repo, "commit", "-m", "initial", capture_output=True)
    server = MCPServer(McpServerConfig(workspace_path=tmp_path / "workspace"))
    await server.initialize()
    try:
        registered = await server.call_tool("register_repo", {"repo_path": str(repo)})
        repo_id = registered.payload["repo"]["repo_id"]
        classify = await server.call_tool(
            "classify_repo_question", {"question": "Where is app.py?"}
        )
        blame = await server.call_tool(
            "git_blame_chain", {"repo": repo_id, "file": "app.py", "line": 1}
        )
        contract = await server.call_tool(
            "get_interface_contract",
            {"plugin_id": "http-rest", "interface_name": "missing"},
        )
        answer = await server.call_tool(
            "answer_repo_question",
            {"question": "Where is app.py?", "repos": [repo_id], "synthesis": False},
        )
        assert classify.payload["question_class"] == "file-loc"
        assert blame.payload["entries"]
        assert contract.status == "not_found"
        assert answer.payload["confidence"] == "unknown"
    finally:
        await server.close()
