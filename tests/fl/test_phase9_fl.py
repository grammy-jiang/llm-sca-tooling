"""Phase 9 fault-localisation tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from llm_sca_tooling.fl.blame_prior import blame_prior, recency_decay
from llm_sca_tooling.fl.context_assembler import assemble_context
from llm_sca_tooling.fl.embedding_adapters import NullEmbeddingAdapter
from llm_sca_tooling.fl.embedding_adapters.local_adapter import LocalEmbeddingAdapter
from llm_sca_tooling.fl.embedding_adapters.openai_adapter import OpenAIEmbeddingAdapter
from llm_sca_tooling.fl.embedding_interface import EmbeddingUnavailable, make_vector
from llm_sca_tooling.fl.graph_expansion import expand_graph_neighbours
from llm_sca_tooling.fl.investigate import (
    InvestigateInput,
    investigate,
    render_investigate_prompt,
)
from llm_sca_tooling.fl.issue import normalize_issue_text
from llm_sca_tooling.fl.keyword_retrieval import keyword_retrieve
from llm_sca_tooling.fl.localisation import get_relevant_files
from llm_sca_tooling.fl.memory_stub import MemoryHintStub
from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    CodeSpan,
    ConfidenceLevel,
    LocalisationResult,
    SignalType,
    candidate_id,
)
from llm_sca_tooling.fl.ranking import RankingPolicy, agreement_score
from llm_sca_tooling.fl.reasoning import reason_for_candidate, symbol_candidates
from llm_sca_tooling.fl.sarif_prior import sarif_prior
from llm_sca_tooling.fl.sbfl import ochiai, parse_cobertura, parse_lcov
from llm_sca_tooling.fl.uncertainty import apply_uncertainty
from llm_sca_tooling.fl.vector_cache import VectorCache
from llm_sca_tooling.mcp_server import MCPServer, McpServerConfig
from llm_sca_tooling.qa.blame import BlameEntry, CommitRecord
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


@pytest.fixture()
async def workspace(tmp_path: Path) -> WorkspaceStore:
    return await WorkspaceStore.initialize(tmp_path / "workspace", in_memory=True)


@pytest.fixture()
async def seeded_workspace(workspace: WorkspaceStore, tmp_path: Path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "user_service.py").write_text(
        "def validate(user):\n    return user.name\n"
    )
    repo = await workspace.registry.register_repo(root, name="fl")
    await workspace.snapshots.record_snapshot(
        repo.repo_id, git_sha="abc123", branch="main", index_status="fresh"
    )
    repo_ref = RepoRef(repo_id=repo.repo_id, name="fl", default_branch="main")
    snapshot = SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="abc123",
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )
    provenance = Provenance(
        source_tool="test",
        repo=repo_ref,
        snapshot=snapshot,
        derivation=DerivationType.parser,
        confidence=1.0,
        evidence_strength=EvidenceStrength.hard_static,
        created_ts=NOW,
    )
    file_node = GraphNode(
        node_id="node:file:user_service",
        node_type=GraphNodeType.file,
        label="user_service.py",
        repo=repo_ref,
        snapshot=snapshot,
        provenance=provenance,
        created_ts=NOW,
        file_path="src/user_service.py",
    )
    func_node = GraphNode(
        node_id="node:function:validate",
        node_type=GraphNodeType.function,
        label="validate",
        qualified_name="UserService.validate",
        repo=repo_ref,
        snapshot=snapshot,
        provenance=provenance,
        created_ts=NOW,
        file_path="src/user_service.py",
        span=SourceSpan(file_path="src/user_service.py", start_line=1, end_line=2),
    )
    test_node = GraphNode(
        node_id="node:test:user_service",
        node_type=GraphNodeType.test,
        label="test_validate",
        repo=repo_ref,
        snapshot=snapshot,
        provenance=provenance,
        created_ts=NOW,
        file_path="tests/test_user_service.py",
    )
    await workspace.graph.add_nodes([file_node, func_node, test_node])
    await workspace.graph.add_edge(
        GraphEdge(
            edge_id="edge:tests",
            edge_type=GraphEdgeType.tests,
            source_id=test_node.node_id,
            target_id=func_node.node_id,
            repo=repo_ref,
            snapshot=snapshot,
            provenance=provenance,
            created_ts=NOW,
        )
    )
    return workspace, repo.repo_id


def test_issue_normalizer_extracts_sections_and_stacks() -> None:
    issue = normalize_issue_text("""
        ## Expected
        validation succeeds
        ## Actual
        AttributeError: 'NoneType' object has no attribute 'name'
        Traceback (most recent call last):
          File "src/user_service.py", line 2, in validate
        at callApi (src/client.ts:12:1)
        #0 0x0 in Service::run (src/service.cpp:42)
        """)
    assert issue.expected_behaviour == "validation succeeds"
    assert issue.observed_behaviour is not None
    assert len(issue.stack_trace_frames) == 3
    assert {"python", "typescript", "cpp"}.issubset(set(issue.language_hints))
    assert "src/user_service.py" in issue.mentioned_files
    assert any("AttributeError" in error for error in issue.error_strings)


async def test_keyword_ranking_context_and_localisation(seeded_workspace) -> None:
    workspace, repo_id = seeded_workspace
    issue = normalize_issue_text(
        'AttributeError in UserService.validate\nFile "src/user_service.py", line 2, in validate',
        repos=[repo_id],
    )
    candidates = await keyword_retrieve(workspace, issue, [repo_id])
    expanded = await expand_graph_neighbours(workspace, candidates[:1])
    context = await assemble_context(workspace, issue, candidates, max_files=8)
    result, bundle = await get_relevant_files(
        workspace,
        issue_text=issue.raw_text,
        repos=[repo_id],
        include_symbols=True,
    )
    assert candidates[0].file_path == "src/user_service.py"
    assert expanded and expanded[0].file_path == "tests/test_user_service.py"
    assert context.files[0].exact_spans
    assert result.ranked_files[0].file_path == "src/user_service.py"
    assert result.ranked_symbols
    assert bundle.files


def test_embedding_interface_and_vector_cache_models() -> None:
    adapter = NullEmbeddingAdapter()
    assert LocalEmbeddingAdapter().is_available() is False
    assert OpenAIEmbeddingAdapter().is_available() is False
    vector = make_vector("a", [1.0, 0.0], "test")
    other = make_vector("b", [0.0, 1.0], "test")
    assert adapter.is_available() is False
    with pytest.raises(EmbeddingUnavailable):
        adapter.embed_text("x")
    assert adapter.similarity(vector, other) == 0.0
    assert adapter.top_k_similar(vector, [other, vector], 2)[0][0] == 1


async def test_vector_cache_store_get_invalidate(workspace: WorkspaceStore) -> None:
    cache = VectorCache(workspace)
    vector = make_vector("hello", [1.0], "test")
    await cache.store(
        "node:1", "test", "sha1", vector, repo_id="repo:test", file_path="src/app.py"
    )
    assert await cache.get("node:1", "test", "sha1") == vector
    assert await cache.get("node:1", "test", "sha2") is None
    assert (await cache.stats()).hit_rate == 0.5
    assert await cache.invalidate_file("src/app.py", "repo:test", "sha2") == 1
    await cache.store("node:2", "test", "old", vector, repo_id="repo:test")
    assert await cache.invalidate_repo("repo:test", "new") == 1
    await cache.store(
        "node:3",
        "test",
        "sha",
        vector,
        repo_id="repo:test",
        expires_ts=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    )
    assert await cache.purge_expired() == 1


def test_sarif_blame_sbfl_and_ranking() -> None:
    issue = normalize_issue_text("CWE-79 security error in validate")
    alert = SimpleNamespace(
        suppression_state=None,
        location=SimpleNamespace(file_path="src/user_service.py"),
        normalized_severity=SimpleNamespace(value="high"),
        message="security error in validate",
        rule=SimpleNamespace(rule_id="CWE-79", name="xss"),
        alert_id="alert:1",
    )
    sarif = sarif_prior(issue, [alert], repo_id="repo:test", snapshot_id="sha")
    suppressed = SimpleNamespace(
        suppressed=True,
        file_path="src/suppressed.py",
        normalized_severity=SimpleNamespace(value="high"),
        message="security",
        rule_id="CWE-79",
        alert_id="alert:suppressed",
    )
    no_file = SimpleNamespace(
        suppressed=False,
        normalized_severity=SimpleNamespace(value="high"),
        message="security",
        rule_id="CWE-79",
        alert_id="alert:no-file",
    )
    symbol_alert = SimpleNamespace(
        suppressed=False,
        file_path="src/symbol.py",
        normalized_severity=SimpleNamespace(value="medium"),
        message="UserService.validate",
        rule_id="rule",
        alert_id="alert:symbol",
    )
    security_alert = SimpleNamespace(
        suppressed=False,
        file_path="src/security.py",
        normalized_severity=SimpleNamespace(value="high"),
        message="generic",
        rule_id="rule",
        alert_id="alert:security",
    )
    recent = str(int(datetime.now(UTC).timestamp()))
    blame = blame_prior(
        issue,
        [
            BlameEntry(
                repo_id="repo:test",
                file_path="src/user_service.py",
                line_start=1,
                line_end=1,
                commit=CommitRecord(
                    commit_sha="abc",
                    author="dev",
                    author_time=recent,
                    summary="fix validate security error",
                ),
            )
        ],
        snapshot_id="sha",
    )
    churn_blame = blame_prior(
        normalize_issue_text("regression without matching summary"),
        [
            BlameEntry(
                repo_id="repo:test",
                file_path="src/churn.py",
                line_start=1,
                line_end=1,
                commit=CommitRecord(
                    commit_sha="def",
                    author="dev",
                    author_time="not-a-time",
                    summary="misc",
                ),
            ),
            BlameEntry(
                repo_id="repo:test",
                file_path="src/churn.py",
                line_start=2,
                line_end=2,
                commit=CommitRecord(
                    commit_sha="ghi",
                    author="dev",
                    author_time=datetime.now(UTC).isoformat(),
                    summary="misc",
                ),
            ),
        ],
        snapshot_id="sha",
    )
    ranked = RankingPolicy().merge([sarif, blame], max_files=8)
    assert sarif[0].combined_score == 1.0
    assert (
        sarif_prior(
            issue, [suppressed, no_file], repo_id="repo:test", snapshot_id="sha"
        )
        == []
    )
    assert sarif_prior(
        normalize_issue_text("UserService.validate failed"),
        [symbol_alert],
        repo_id="repo:test",
        snapshot_id="sha",
    )
    assert sarif_prior(
        normalize_issue_text("security vulnerability"),
        [security_alert],
        repo_id="repo:test",
        snapshot_id="sha",
    )
    assert blame[0].combined_score > 0.0
    assert churn_blame[0].file_path == "src/churn.py"
    assert recency_decay("not-a-time") == 0.0
    assert recency_decay(recent) > 0.9
    assert ranked[0].confidence == ConfidenceLevel.analyser
    assert agreement_score(ranked[0].signals) >= 0.5
    assert ochiai(3, 1, 0, 3) == pytest.approx(0.866, rel=0.01)


def test_coverage_parsers_and_uncertainty(tmp_path: Path) -> None:
    lcov = tmp_path / "lcov.info"
    lcov.write_text("SF:src/app.py\nDA:1,3\nend_of_record\n")
    cobertura = tmp_path / "coverage.xml"
    cobertura.write_text(
        '<coverage><packages><package><classes><class filename="src/app.py">'
        '<lines><line number="1" hits="2"/></lines></class></classes></package>'
        "</packages></coverage>"
    )
    assert parse_lcov(lcov)[0].line_coverage[1] == 3
    assert parse_cobertura(cobertura)[0].line_coverage[1] == 2
    result = LocalisationResult(
        ranked_files=[],
        agreement_score=0.0,
        confidence=ConfidenceLevel.analyser,
    )
    uncertain = apply_uncertainty(
        result,
        embedding_available=False,
        graph_stale=True,
        budget_exceeded=True,
        all_frames_unresolved=True,
        sarif_stale=True,
    )
    assert uncertain.confidence == ConfidenceLevel.heuristic
    assert "Embedding retrieval unavailable" in (uncertain.uncertainty or "")


async def test_investigate_and_mcp_tool(seeded_workspace, tmp_path: Path) -> None:
    workspace, repo_id = seeded_workspace
    payload = InvestigateInput(
        issue_text='AttributeError\nFile "src/user_service.py", line 2, in validate',
        repos=[repo_id],
    )
    output = await investigate(workspace, payload)
    prompt = render_investigate_prompt(payload, output.localisation_result)
    assert output.reasoning_chains
    assert output.provenance.memory_phase == "stub"
    assert "Fault Localisation" in prompt
    server = MCPServer(McpServerConfig(workspace_path=tmp_path / "mcp"))
    await server.initialize()
    try:
        registered = await server.call_tool(
            "register_repo",
            {"repo_path": str(tmp_path), "name": "empty"},
        )
        result = await server.call_tool(
            "get_relevant_files",
            {
                "issue_text": "unknown issue",
                "repos": [registered.payload["repo"]["repo_id"]],
            },
        )
        assert "ranked_files" in result.payload
    finally:
        await server.close()


def test_reasoning_memory_and_model_validators() -> None:
    signal = CandidateSignal(
        signal_type=SignalType.keyword,
        raw_score=1.0,
        weight=0.25,
        weighted_score=0.25,
        evidence="exact match",
        source_refs=["node:1"],
    )
    candidate = CandidateFile(
        candidate_id=candidate_id("repo:test", "src/app.py"),
        file_path="src/app.py",
        repo_id="repo:test",
        node_id="node:1",
        signals=[signal],
        combined_score=1.0,
        snapshot_id="sha",
    )
    with pytest.raises(ValueError):
        CodeSpan(
            file_path="src/app.py",
            start_line=1,
            end_line=20,
            content="\n".join(str(i) for i in range(11)),
            confidence=ConfidenceLevel.heuristic,
            reason="test",
        )
    assert (
        MemoryHintStub().retrieve_fl_hints(normalize_issue_text("x"), 3).hints_used
        == []
    )
    context = SimpleNamespace(
        graph_slice={
            "nodes": [{"node_id": "node:1", "node_type": "function", "label": "f"}]
        }
    )
    assert "exact match" in reason_for_candidate(candidate, context)  # type: ignore[arg-type]
    assert symbol_candidates(
        [candidate],
        [SimpleNamespace(candidate_file=candidate, graph_slice=context.graph_slice)],
    )  # type: ignore[list-item]
