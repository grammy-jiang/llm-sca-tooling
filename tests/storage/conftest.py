from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from llm_sca_tooling.schemas.enums import DerivationType, EvidenceStrength, GraphEdgeType, GraphNodeType, IndexStatus, PolicyAction, RedactionStatus, Status
from llm_sca_tooling.schemas.governance import ContextBudget, ManifestHash, RedactionPolicy, RetryPolicy, RuntimeRef, SandboxDescriptor, ToolPermission, VerificationGate
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.schemas.harness import HarnessCondition, SamplingCapability
from llm_sca_tooling.schemas.provenance import ArtifactRef, Provenance, RepoRef, SnapshotRef, SourceSpan
from llm_sca_tooling.schemas.run_records import Actor, RunEvent, RunEventType, RunRecord, Workflow
from llm_sca_tooling.storage import WorkspaceStore, initialize_workspace

TS = "2026-05-09T00:00:00Z"


@pytest.fixture
def workspace(tmp_path: Path) -> WorkspaceStore:
    store = initialize_workspace(tmp_path / ".llm-sca")
    yield store
    store.close()


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".git").mkdir()
    return root


@pytest.fixture
def registered_repo(workspace: WorkspaceStore, repo_root: Path):
    return workspace.repositories.register_repo(repo_root, name="demo")


@pytest.fixture
def repo_ref(registered_repo) -> RepoRef:
    return RepoRef(repo_id=registered_repo.repo_id, name=registered_repo.name, default_branch=registered_repo.default_branch)


@pytest.fixture
def snapshot(repo_ref: RepoRef) -> SnapshotRef:
    return SnapshotRef(
        repo_id=repo_ref.repo_id,
        git_sha="0123456789abcdef0123456789abcdef01234567",
        branch="main",
        worktree_snapshot_id=None,
        dirty=False,
        index_status=IndexStatus.FRESH,
        captured_ts=TS,
    )


@pytest.fixture
def dirty_snapshot(repo_ref: RepoRef) -> SnapshotRef:
    return SnapshotRef(
        repo_id=repo_ref.repo_id,
        git_sha="0123456789abcdef0123456789abcdef01234567",
        branch="main",
        worktree_snapshot_id="dirty:1",
        dirty=True,
        index_status=IndexStatus.PARTIAL,
        captured_ts=TS,
    )


@pytest.fixture
def provenance(repo_ref: RepoRef, snapshot: SnapshotRef) -> Provenance:
    return Provenance(
        source_tool="test",
        source_version="0.1",
        source_run_id="run:demo",
        source_event_id="event:run:demo:1",
        repo=repo_ref,
        snapshot=snapshot,
        derivation=DerivationType.PARSER,
        confidence=1.0,
        evidence_strength=EvidenceStrength.HARD_STATIC,
        created_ts=TS,
        attributes={},
    )


def graph_node(node_id: str, node_type: GraphNodeType, repo: RepoRef, snapshot: SnapshotRef, provenance: Provenance, *, file_path: str | None = None) -> GraphNode:
    span = SourceSpan(file_path=file_path, start_line=1, end_line=10) if file_path else None
    return GraphNode(
        node_id=node_id,
        node_type=node_type,
        label=node_id,
        qualified_name=node_id if node_type in {GraphNodeType.FUNCTION, GraphNodeType.METHOD, GraphNodeType.CLASS} else None,
        repo=repo,
        snapshot=snapshot,
        file_path=file_path,
        span=span,
        provenance=provenance,
        properties={},
        created_ts=TS,
    )


def graph_edge(edge_id: str, source: GraphNode, target: GraphNode, provenance: Provenance, edge_type: GraphEdgeType = GraphEdgeType.CALLS) -> GraphEdge:
    return GraphEdge(
        edge_id=edge_id,
        edge_type=edge_type,
        source_id=source.node_id,
        target_id=target.node_id,
        repo=source.repo,
        snapshot=source.snapshot,
        provenance=provenance,
        confidence=1.0,
        properties={},
        created_ts=TS,
    )


def artifact_ref(path: Path) -> ArtifactRef:
    payload = path.read_bytes()
    return ArtifactRef(
        artifact_id="art:test",
        kind="log",
        uri=str(path),
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        media_type="text/plain",
        redaction_status=RedactionStatus.REDACTED,
        created_ts=TS,
    )


def run_record(repo_ref: RepoRef, event_count: int = 0, status: Status = Status.RUNNING) -> RunRecord:
    return RunRecord(
        run_id="run:demo",
        workflow=Workflow.IMPLEMENTATION_CHECK,
        user_intent_hash="hash:intent",
        repos=[repo_ref],
        start_ts=TS,
        end_ts=TS if status == Status.COMPLETED else None,
        status=status,
        toolset_hash="hash:tools",
        policy_id="policy:default",
        permission_profile="default",
        context_budget=ContextBudget(max_tokens=1000),
        run_event_count=event_count,
        harness_condition_id="harness:demo",
        redaction_policy=RedactionPolicy(policy_id="redaction:default", default_status=RedactionStatus.REDACTED),
        created_ts=TS,
    )


def run_event(seq: int, event_type: RunEventType = RunEventType.POLICY_DECISION) -> RunEvent:
    return RunEvent(
        event_id=f"event:run:demo:{seq}",
        run_id="run:demo",
        seq=seq,
        ts=TS,
        type=event_type,
        actor=Actor.POLICY,
        stage="policy",
        policy_action=PolicyAction.DENY,
        artefact_ids=[],
        redaction_status=RedactionStatus.NOT_REQUIRED,
        payload={"reason": "test"},
    )


def harness_condition(provenance: Provenance) -> HarnessCondition:
    return HarnessCondition(
        harness_condition_id="harness:demo",
        run_id="run:demo",
        captured_ts=TS,
        runtime=RuntimeRef(runtime_id="runtime:copilot", name="copilot-cli"),
        manifest_hashes=[ManifestHash(path="AGENTS.md", sha256="hash")],
        toolset_hash="hash:tools",
        exposed_tools=[
            ToolPermission(
                tool_name="apply_patch",
                required_mode="edit",
                path_scope="repo",
                network_requirement="none",
                side_effect_class="writes_repo",
                approval_requirement="not_required",
            )
        ],
        permission_profile="default",
        sandbox=SandboxDescriptor(kind="devcontainer", writes_allowed=True, network_allowed=False, path_scope="repo"),
        network_policy="deny-by-default",
        context_policy=ContextBudget(max_tokens=1000),
        retry_policy=RetryPolicy(max_retries=1),
        verification_gates=[VerificationGate(gate_name="pytest", gate_type="unit_test", required=True)],
        telemetry_location=".agent/logs",
        redaction_policy=RedactionPolicy(policy_id="redaction:default", default_status=RedactionStatus.REDACTED),
        sampling_capability=SamplingCapability.UNKNOWN,
        provenance=provenance,
    )
