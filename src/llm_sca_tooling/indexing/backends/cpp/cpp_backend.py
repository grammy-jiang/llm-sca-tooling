"""Unified C/C++ backend."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.backends.base import (
    BackendAvailability,
    BackendCapabilityDescriptor,
    BackendResult,
)
from llm_sca_tooling.indexing.backends.cpp.abi_edge_builder import AbiEdgeBuilder
from llm_sca_tooling.indexing.backends.cpp.clangd_adapter import ClangdAdapter
from llm_sca_tooling.indexing.backends.cpp.cmake_backend import CMakeBackend
from llm_sca_tooling.indexing.backends.cpp.compile_commands import CompileCommands
from llm_sca_tooling.indexing.backends.cpp.ctest_detection import detect_ctest
from llm_sca_tooling.indexing.backends.cpp.libclang_adapter import LibclangAdapter
from llm_sca_tooling.indexing.backends.fact_reconciler import FactReconciler
from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.schemas.enums import (
    DerivationType,
    EvidenceStrength,
    GraphEdgeType,
    GraphNodeType,
    Severity,
)
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts


class CppBackend:
    backend_id = "cpp.backend"

    def __init__(self) -> None:
        self.compile_commands = CompileCommands()
        self.libclang = LibclangAdapter()
        self.clangd = ClangdAdapter()
        self.reconciler = FactReconciler()

    def backend_version(self) -> str:
        return "0.1.0"

    def check_availability(self) -> BackendAvailability:
        return BackendAvailability(
            backend_id=self.backend_id,
            available=True,
            tool_version=self.backend_version(),
        )

    def describe_capabilities(self) -> BackendCapabilityDescriptor:
        return BackendCapabilityDescriptor(
            backend_id=self.backend_id,
            backend_version=self.backend_version(),
            supported_node_types=[
                GraphNodeType.MODULE,
                GraphNodeType.CLASS,
                GraphNodeType.FUNCTION,
                GraphNodeType.BUILD_TARGET,
                GraphNodeType.CI_JOB,
            ],
            supported_edge_types=[
                GraphEdgeType.CONTAINS,
                GraphEdgeType.IMPORTS,
                GraphEdgeType.CALLS,
                GraphEdgeType.OWNS,
            ],
            max_confidence=EvidenceStrength.HARD_STATIC,
            derivation=DerivationType.PARSER,
            can_resolve_cross_file_calls=True,
            requires_compile_commands=True,
            incremental_support=True,
            languages=["c", "cpp"],
        )

    def index_files(
        self,
        repo_root: Path,
        repo: RepoRef,
        snapshot: SnapshotRef,
        files: list[ScannedFile],
        *,
        run_id: str | None = None,
    ) -> BackendResult:
        commands, command_diags = self.compile_commands.load(repo_root)
        libclang_result = self.libclang.index_files(
            repo_root, repo, snapshot, files, commands, run_id=run_id
        )
        clangd_result = self.clangd.index_files(
            repo_root, repo, snapshot, files, run_id=run_id
        )
        reconciled = self.reconciler.reconcile([libclang_result, clangd_result])
        result = BackendResult(
            backend_id=self.backend_id,
            backend_version=self.backend_version(),
            started_ts=libclang_result.started_ts,
            ended_ts=_now_ts(),
        )
        result.nodes = AbiEdgeBuilder().annotate_public_symbols(reconciled.nodes)
        result.edges = reconciled.edges
        result.diagnostics = [
            *libclang_result.diagnostics,
            *clangd_result.diagnostics,
            *reconciled.diagnostics,
        ]
        for code in command_diags:
            result.diagnostics.append(
                IndexDiagnostic(
                    diagnostic_id=f"diag:cpp:{code.lower()}",
                    severity=Severity.INFO,
                    code=code,
                    message="C/C++ analysis degraded because compile_commands.json is missing",
                )
            )
        result.capabilities_used = [
            "cpp.libclang",
            "cpp.clangd",
            "cpp.cmake",
            "cpp.ctest",
        ]
        result.files_processed = libclang_result.files_processed
        result.run_stats.files_scanned = len(
            [file for file in files if file.language in {"c", "cpp"}]
        )
        result.run_stats.nodes_emitted = len(result.nodes)
        result.run_stats.edges_emitted = len(result.edges)
        result.run_stats.diagnostics_emitted = len(result.diagnostics)
        result.output_hash = str(
            len(CMakeBackend().detect_targets(repo_root)) + len(detect_ctest(repo_root))
        )
        return result
