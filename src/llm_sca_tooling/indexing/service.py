"""Indexing service and graph build/update entrypoints."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

from llm_sca_tooling.indexing.backends.ctags import CtagsBackend
from llm_sca_tooling.indexing.backends.cpp import CppBackend
from llm_sca_tooling.indexing.backends.java import JavaBackend
from llm_sca_tooling.indexing.backends.python import PythonBackend
from llm_sca_tooling.indexing.backends.tree_sitter import TreeSitterBackend
from llm_sca_tooling.indexing.backends.typescript import TypeScriptBackend
from llm_sca_tooling.indexing.build_evidence import BuildTestEvidenceDetector
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic, RepositoryResolutionError
from llm_sca_tooling.indexing.git_metadata import capture_snapshot, changed_files_since_latest
from llm_sca_tooling.indexing.graph_slices import GraphSliceGenerator
from llm_sca_tooling.indexing.manifests import GraphManifestGenerator
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.indexing.result import IndexingResult
from llm_sca_tooling.indexing.scanner import FileScanner, ScannedFile
from llm_sca_tooling.indexing.summaries import SummaryCache
from llm_sca_tooling.schemas.enums import DerivationType, EvidenceStrength, IndexStatus, PermissionMode, PolicyAction, RedactionStatus, Severity, SideEffectClass, Status
from llm_sca_tooling.schemas.governance import ContextBudget, ManifestHash, RedactionPolicy, RetryPolicy, RuntimeRef, SandboxDescriptor, ToolPermission, VerificationGate
from llm_sca_tooling.schemas.graph import GraphDiagnostic, GraphEdge, GraphNode
from llm_sca_tooling.schemas.harness import HarnessCondition, SamplingCapability
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.schemas.run_records import Actor, RunEvent, RunEventType, RunRecord, Workflow
from llm_sca_tooling.storage import WorkspaceStore, initialize_workspace
from llm_sca_tooling.storage.graph_queries import GraphSlice
from llm_sca_tooling.storage.ids import payload_hash, snapshot_id_for
from llm_sca_tooling.storage.workspace import _now_ts


class IndexingService:
    def __init__(self, workspace: WorkspaceStore, config: IndexingConfig | None = None) -> None:
        self.workspace = workspace
        self.config = config or IndexingConfig()
        self.scanner = FileScanner(self.config)
        self.python_backend = PythonBackend()
        self.typescript_backend = TypeScriptBackend()
        self.cpp_backend = CppBackend()
        self.java_backend = JavaBackend()
        self.ctags_backend = CtagsBackend()
        self.tree_sitter_backend = TreeSitterBackend()
        self.build_evidence = BuildTestEvidenceDetector()
        self.manifests = GraphManifestGenerator(workspace)
        self.summaries = SummaryCache(workspace.storage_root / "summaries")
        self.slices = GraphSliceGenerator(workspace)

    def graph_build(self, repo_path: str | Path, *, config: IndexingConfig | None = None) -> IndexingResult:
        return self._build(repo_path, update_only=False, override_config=config)

    def graph_update(self, repo_path: str | Path, *, config: IndexingConfig | None = None) -> IndexingResult:
        return self._build(repo_path, update_only=True, override_config=config)

    def get_graph_slice(self, repo_id: str, *, files: list[str] | None = None, symbols: list[str] | None = None, depth: int = 1) -> GraphSlice:
        if files:
            return self.slices.by_file(repo_id, files[0], depth=depth, limit=self.config.graph_slice_limit)
        if symbols:
            return self.slices.by_symbol(repo_id, symbols[0], depth=depth, limit=self.config.graph_slice_limit)
        raise ValueError("files or symbols must be provided")

    def _build(self, repo_path: str | Path, *, update_only: bool, override_config: IndexingConfig | None) -> IndexingResult:
        config = override_config or self.config
        started = _now_ts()
        repo_root = Path(repo_path).expanduser().resolve()
        if not repo_root.exists():
            raise RepositoryResolutionError(f"repo path does not exist: {repo_root}")
        repo_row = self.workspace.repositories.register_repo(repo_root)
        repo = RepoRef(repo_id=repo_row.repo_id, name=repo_row.name, root_ref=repo_row.root_path_hash, remote_url_hash=repo_row.remote_url_hash, default_branch=repo_row.default_branch)
        snapshot, snapshot_id, git_metadata = capture_snapshot(repo.repo_id, repo_root, config)
        self.workspace.snapshots.record_snapshot(snapshot, snapshot_id=snapshot_id)
        run_id = f"run:index:{uuid.uuid4().hex}"
        run_record = self._run_record(run_id, repo, snapshot, status=Status.RUNNING)
        self.workspace.operations.create_run(run_record)
        self._record_harness(run_id, repo, snapshot)
        self._event(run_id, RunEventType.SESSION_START, Actor.SYSTEM, "indexing", {"repo_id": repo.repo_id})
        self._event(run_id, RunEventType.HARNESS_CONDITION_RECORDED, Actor.SYSTEM, "indexing", {"harness_condition_id": run_record.harness_condition_id})
        self._event(run_id, RunEventType.STAGE_COMPLETED, Actor.SYSTEM, "snapshot", {"snapshot_id": snapshot_id, "dirty": snapshot.dirty, "changed_files": git_metadata.changed_files})
        self.workspace.repositories.update_repo_status(repo.repo_id, "indexing")
        scan_result = self.scanner.scan(repo_root, repo, snapshot, run_id=run_id)
        selected_files = scan_result.files
        changed_files = changed_files_since_latest(repo_root, git_metadata)
        stale_summary_count = 0
        if update_only and changed_files:
            selected_files = [file for file in scan_result.files if file.path in changed_files]
            stale_summary_count = self.summaries.invalidate_for_files(changed_files, "graph_update")
        elif update_only and not changed_files:
            stale_summary_count = 0
        if update_only:
            self._event(run_id, RunEventType.STAGE_COMPLETED, Actor.TOOL, "summaries", {"invalidated": stale_summary_count, "changed_files": changed_files})
        self._event(run_id, RunEventType.STAGE_COMPLETED, Actor.TOOL, "scanner", {"files_scanned": len(scan_result.files), "files_skipped": scan_result.files_skipped})
        backend_results = []
        backend_results.append(self.python_backend.index_files(repo_root, repo, snapshot, selected_files, run_id=run_id))
        backend_results.append(self.typescript_backend.index_files(repo_root, repo, snapshot, selected_files, run_id=run_id))
        backend_results.append(self.cpp_backend.index_files(repo_root, repo, snapshot, selected_files, run_id=run_id))
        backend_results.append(self.java_backend.index_files(repo_root, repo, snapshot, selected_files, run_id=run_id))
        backend_results.append(self.build_evidence.detect(repo_root, repo, snapshot, selected_files if update_only and changed_files else scan_result.files, run_id=run_id))
        if config.run_optional_backends:
            backend_results.append(self.ctags_backend.index_files(repo_root, repo, snapshot, selected_files, run_id=run_id))
            backend_results.append(self.tree_sitter_backend.index_files(repo_root, repo, snapshot, selected_files, run_id=run_id))
        for backend in backend_results:
            self._event(run_id, RunEventType.STAGE_COMPLETED, Actor.TOOL, "backend", {"backend_id": backend.backend_id, "version": backend.backend_version, "files_processed": len(backend.files_processed), "diagnostics": len(backend.diagnostics)})
        nodes, edges, diagnostics = self._merge(scan_result.nodes if not update_only else [node for node in scan_result.nodes if not node.file_path or node.file_path in set(changed_files)], scan_result.edges if not update_only else [], backend_results)
        self._write_graph(nodes, edges)
        self._event(run_id, RunEventType.STAGE_COMPLETED, Actor.TOOL, "graph", {"persisted": True, "nodes": len(nodes), "edges": len(edges)})
        graph_diagnostics = [self._graph_diagnostic(repo, snapshot, diagnostic, run_id=run_id) for diagnostic in [*scan_result.diagnostics, *diagnostics]]
        for diagnostic in graph_diagnostics:
            self.workspace.conn.execute(
                "INSERT OR REPLACE INTO graph_diagnostics(diagnostic_id, repo_id, snapshot_id, severity, code, message, affected_node_ids_json, affected_edge_ids_json, provenance_json, created_ts) VALUES (?, ?, ?, ?, ?, ?, '[]', '[]', ?, ?)",
                (diagnostic.diagnostic_id, repo.repo_id, snapshot_id, diagnostic.severity.value, diagnostic.code, diagnostic.message, diagnostic.provenance.model_dump_json() if diagnostic.provenance else None, _now_ts()),
            )
        self.workspace.conn.commit()
        manifest_id, artifact_refs = self.manifests.generate(repo.repo_id, snapshot_id, run_id, chunk_size=config.manifest_chunk_size)
        for artifact in artifact_refs:
            self._event(run_id, RunEventType.STAGE_COMPLETED, Actor.TOOL, "manifest", {"artifact_id": artifact.artifact_id})
        all_diagnostics = [*scan_result.diagnostics, *diagnostics]
        status = "fresh" if all(diagnostic.severity == Severity.INFO for diagnostic in all_diagnostics) else "partial"
        self.workspace.repositories.update_repo_status(repo.repo_id, status)
        self.workspace.repositories.set_latest_snapshot(repo.repo_id, snapshot_id)
        self.workspace.snapshots.mark_snapshot_status(snapshot_id, IndexStatus.FRESH if status == "fresh" else IndexStatus.PARTIAL)
        if snapshot.dirty:
            self._event(run_id, RunEventType.MONITOR_ALERT, Actor.MONITOR, "snapshot", {"warning": "dirty_snapshot", "snapshot_id": snapshot_id})
        self._event(run_id, RunEventType.FINAL_VERDICT_RECORDED, Actor.SYSTEM, "indexing", {"status": status, "nodes": len(nodes), "edges": len(edges)})
        self.workspace.operations.close_run(run_id, Status.COMPLETED, end_ts=_now_ts())
        ended = _now_ts()
        return IndexingResult(
            repo_id=repo.repo_id,
            run_id=run_id,
            snapshot_id=snapshot_id,
            status=status,
            files_scanned=len(scan_result.files),
            files_indexed=len(selected_files),
            files_skipped=scan_result.files_skipped,
            changed_files=changed_files if update_only else [],
            nodes_added=len(nodes),
            edges_added=len(edges),
            diagnostics=all_diagnostics,
            graph_manifest_id=manifest_id,
            artifact_refs=[artifact.artifact_id for artifact in artifact_refs],
            stale_summary_count=stale_summary_count,
            backend_versions={backend.backend_id: backend.backend_version for backend in backend_results},
            started_ts=started,
            ended_ts=ended,
        )

    def _merge(self, scanner_nodes: list[GraphNode], scanner_edges: list[GraphEdge], backend_results) -> tuple[list[GraphNode], list[GraphEdge], list[IndexDiagnostic]]:
        nodes: dict[str, GraphNode] = {}
        edges: dict[str, GraphEdge] = {}
        diagnostics: list[IndexDiagnostic] = []
        for node in scanner_nodes:
            nodes[node.node_id] = node
        for edge in scanner_edges:
            edges[edge.edge_id] = edge
        for result in backend_results:
            diagnostics.extend(result.diagnostics)
            for node in result.nodes:
                existing = nodes.get(node.node_id)
                if existing and payload_hash(existing.model_dump(mode="json")) != payload_hash(node.model_dump(mode="json")):
                    diagnostics.append(IndexDiagnostic(diagnostic_id=f"diag:merge:{node.node_id[-12:]}", severity=Severity.INFO, code="duplicate_node_merged", message=f"Duplicate node retained from first backend: {node.node_id}"))
                    continue
                nodes[node.node_id] = node
            for edge in result.edges:
                existing = edges.get(edge.edge_id)
                if existing and payload_hash(existing.model_dump(mode="json")) != payload_hash(edge.model_dump(mode="json")):
                    diagnostics.append(IndexDiagnostic(diagnostic_id=f"diag:merge:{edge.edge_id[-12:]}", severity=Severity.INFO, code="duplicate_edge_merged", message=f"Duplicate edge retained from first backend: {edge.edge_id}"))
                    continue
                edges[edge.edge_id] = edge
        return list(nodes.values()), list(edges.values()), diagnostics

    def _write_graph(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        for node in nodes:
            self.workspace.graph.upsert_node(node)
        for edge in edges:
            self.workspace.graph.upsert_edge(edge)

    def _run_record(self, run_id: str, repo: RepoRef, snapshot: SnapshotRef, *, status: Status) -> RunRecord:
        return RunRecord(
            run_id=run_id,
            workflow=Workflow.GRAPH_BUILD,
            user_intent_hash="indexing",
            repos=[repo],
            start_ts=_now_ts(),
            end_ts=None,
            status=status,
            toolset_hash="indexing:0.1.0",
            policy_id="indexing-default",
            permission_profile="read-only-indexing",
            context_budget=ContextBudget(max_tokens=0, max_tool_calls=0),
            run_event_count=0,
            harness_condition_id=f"harness:{run_id}",
            redaction_policy=RedactionPolicy(policy_id="redaction:indexing", default_status=RedactionStatus.REDACTED),
            created_ts=_now_ts(),
        )

    def _record_harness(self, run_id: str, repo: RepoRef, snapshot: SnapshotRef) -> None:
        provenance = make_provenance(source_tool="evidence-sca.indexing", repo=repo, snapshot=snapshot, source_run_id=run_id)
        condition = HarnessCondition(
            harness_condition_id=f"harness:{run_id}",
            run_id=run_id,
            captured_ts=_now_ts(),
            runtime=RuntimeRef(runtime_id="python", name="python", version=sys.version.split()[0]),
            manifest_hashes=[ManifestHash(path="indexing-config", sha256=payload_hash(self.config.model_dump(mode="json")))],
            toolset_hash="indexing:0.1.0",
            exposed_tools=[ToolPermission(tool_name="filesystem-read", required_mode=PermissionMode.READ, path_scope="repo", network_requirement="none", side_effect_class=SideEffectClass.READ_ONLY, approval_requirement="not_required")],
            permission_profile="read-only-indexing",
            sandbox=SandboxDescriptor(kind="local", writes_allowed=True, network_allowed=False, path_scope="repo"),
            network_policy="deny",
            context_policy=ContextBudget(max_tokens=0, max_tool_calls=0),
            retry_policy=RetryPolicy(max_retries=0),
            verification_gates=[VerificationGate(gate_name="schema-validation", gate_type="custom", required=True)],
            telemetry_location=".llm-sca/workspace.db",
            redaction_policy=RedactionPolicy(policy_id="redaction:indexing", default_status=RedactionStatus.REDACTED),
            sampling_capability=SamplingCapability.UNSUPPORTED,
            supply_chain_refs=[],
            provenance=provenance,
        )
        self.workspace.operations.record_harness_condition(condition)

    def _event(self, run_id: str, event_type: RunEventType, actor: Actor, stage: str, payload: dict) -> None:
        seq = self.workspace.operations.get_run(run_id).run.run_event_count + 1
        event = RunEvent(
            event_id=f"event:{run_id}:{seq}",
            run_id=run_id,
            seq=seq,
            ts=_now_ts(),
            type=event_type,
            actor=actor,
            stage=stage,
            policy_action=PolicyAction.NOT_APPLICABLE,
            artefact_ids=[],
            redaction_status=RedactionStatus.REDACTED,
            payload=payload,
        )
        self.workspace.operations.append_run_event(run_id, event)

    def _graph_diagnostic(self, repo: RepoRef, snapshot: SnapshotRef, diagnostic: IndexDiagnostic, *, run_id: str) -> GraphDiagnostic:
        provenance = make_provenance(
            source_tool="evidence-sca.indexing",
            repo=repo,
            snapshot=snapshot,
            source_run_id=run_id,
            derivation=DerivationType.HEURISTIC,
            evidence_strength=EvidenceStrength.STRUCTURED_REPOSITORY,
            confidence=0.5,
        )
        return GraphDiagnostic(
            diagnostic_id=diagnostic.diagnostic_id,
            severity=diagnostic.severity,
            code=diagnostic.code,
            message=diagnostic.message,
            affected_node_ids=[],
            affected_edge_ids=[],
            provenance=provenance,
        )


def graph_build(repo_path: str | Path, *, workspace_path: str | Path | None = None, config: IndexingConfig | None = None) -> IndexingResult:
    root = Path(repo_path).expanduser().resolve()
    workspace = initialize_workspace(workspace_path or root / (config or IndexingConfig()).workspace_dir_name)
    try:
        return IndexingService(workspace, config).graph_build(root)
    finally:
        workspace.close()


def graph_update(repo_path: str | Path, *, workspace_path: str | Path | None = None, config: IndexingConfig | None = None) -> IndexingResult:
    root = Path(repo_path).expanduser().resolve()
    workspace = initialize_workspace(workspace_path or root / (config or IndexingConfig()).workspace_dir_name)
    try:
        return IndexingService(workspace, config).graph_update(root)
    finally:
        workspace.close()
