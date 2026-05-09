"""clangd capability adapter."""

from __future__ import annotations

import shutil
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import BackendAvailability, BackendCapabilityDescriptor, BackendResult
from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.schemas.enums import DerivationType, EvidenceStrength, GraphEdgeType, GraphNodeType, Severity
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts


class ClangdAdapter:
    backend_id = "cpp.clangd"

    def backend_version(self) -> str:
        return "clangd-lsp-adapter-0.1.0"

    def check_availability(self) -> BackendAvailability:
        path = shutil.which("clangd")
        return BackendAvailability(backend_id=self.backend_id, available=bool(path), tool_path=path, tool_version=self.backend_version(), missing_deps=[] if path else ["clangd"], warnings=[] if path else ["clangd unavailable; LSP reference facts degraded"])

    def describe_capabilities(self) -> BackendCapabilityDescriptor:
        return BackendCapabilityDescriptor(backend_id=self.backend_id, backend_version=self.backend_version(), supported_node_types=[GraphNodeType.SAST_RULE], supported_edge_types=[GraphEdgeType.CALLS, GraphEdgeType.WARNED_BY], max_confidence=EvidenceStrength.STRUCTURED_REPOSITORY, derivation=DerivationType.ANALYSER, can_resolve_cross_file_calls=True, requires_compile_commands=True, lsp_based=True, languages=["c", "cpp"])

    def index_files(self, repo_root: Path, repo: RepoRef, snapshot: SnapshotRef, files: list[ScannedFile], *, run_id: str | None = None) -> BackendResult:
        result = BackendResult(backend_id=self.backend_id, backend_version=self.backend_version(), started_ts=_now_ts(), ended_ts=_now_ts())
        if not self.check_availability().available:
            result.diagnostics.append(IndexDiagnostic(diagnostic_id="diag:cpp.clangd:unavailable", severity=Severity.INFO, code="BACKEND_UNAVAILABLE", message="clangd is unavailable; skipping LSP reference facts"))
        result.run_stats.files_scanned = len([file for file in files if file.language in {"c", "cpp"}])
        result.run_stats.diagnostics_emitted = len(result.diagnostics)
        return result
