"""Unified Python backend."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.backends.base import BackendAvailability, BackendCapabilityDescriptor, BackendResult
from llm_sca_tooling.indexing.backends.fact_reconciler import FactReconciler
from llm_sca_tooling.indexing.backends.python.pyan3_adapter import Pyan3Adapter
from llm_sca_tooling.indexing.backends.python.pyright_adapter import PyrightAdapter
from llm_sca_tooling.indexing.backends.python_ast import PythonAstBackend
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.schemas.enums import DerivationType, EvidenceStrength, GraphEdgeType, GraphNodeType
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts


class PythonBackend:
    backend_id = "python.backend"

    def __init__(self) -> None:
        self.ast = PythonAstBackend()
        self.pyan3 = Pyan3Adapter()
        self.pyright = PyrightAdapter()
        self.reconciler = FactReconciler()

    def backend_version(self) -> str:
        return "0.1.0"

    def check_availability(self) -> BackendAvailability:
        return BackendAvailability(backend_id=self.backend_id, available=True, tool_version=self.backend_version())

    def describe_capabilities(self) -> BackendCapabilityDescriptor:
        return BackendCapabilityDescriptor(backend_id=self.backend_id, backend_version=self.backend_version(), supported_node_types=[GraphNodeType.MODULE, GraphNodeType.CLASS, GraphNodeType.FUNCTION, GraphNodeType.METHOD, GraphNodeType.TEST], supported_edge_types=[GraphEdgeType.CONTAINS, GraphEdgeType.IMPORTS, GraphEdgeType.CALLS, GraphEdgeType.TESTS], max_confidence=EvidenceStrength.HARD_STATIC, derivation=DerivationType.PARSER, can_resolve_cross_file_calls=True, can_resolve_cross_module_calls=True, incremental_support=True, languages=["python"])

    def index_files(self, repo_root: Path, repo: RepoRef, snapshot: SnapshotRef, files: list[ScannedFile], *, run_id: str | None = None) -> BackendResult:
        ast_result = self.ast.index_files(repo_root, repo, snapshot, files, run_id=run_id)
        ast_result.backend_id = "python.ast"
        pyan_result = self.pyan3.index_files(repo_root, repo, snapshot, files, ast_result.nodes, run_id=run_id)
        pyright_result = self.pyright.index_files(repo_root, repo, snapshot, files, run_id=run_id)
        reconciled = self.reconciler.reconcile([ast_result, pyan_result, pyright_result])
        result = BackendResult(backend_id=self.backend_id, backend_version=self.backend_version(), started_ts=ast_result.started_ts, ended_ts=_now_ts())
        result.nodes = reconciled.nodes
        result.edges = reconciled.edges
        result.diagnostics = [*ast_result.diagnostics, *pyan_result.diagnostics, *pyright_result.diagnostics, *reconciled.diagnostics]
        result.files_processed = sorted(set(ast_result.files_processed + pyan_result.files_processed))
        result.files_skipped = sorted(set(ast_result.files_skipped + pyan_result.files_skipped))
        result.capabilities_used = ["python.ast", "python.pyan3", "python.pyright"]
        result.run_stats.files_scanned = len([file for file in files if file.language == "python"])
        result.run_stats.nodes_emitted = len(result.nodes)
        result.run_stats.edges_emitted = len(result.edges)
        result.run_stats.diagnostics_emitted = len(result.diagnostics)
        return result
