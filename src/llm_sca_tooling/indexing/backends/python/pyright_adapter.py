"""Pyright availability and diagnostic adapter."""

from __future__ import annotations

import shutil
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import BackendAvailability, BackendCapabilityDescriptor, BackendResult
from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.schemas.enums import DerivationType, EvidenceStrength, GraphEdgeType, GraphNodeType, Severity
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts


class PyrightAdapter:
    backend_id = "python.pyright"

    def backend_version(self) -> str:
        return "pyright-lsp-adapter-0.1.0"

    def check_availability(self) -> BackendAvailability:
        path = shutil.which("pyright-langserver") or shutil.which("pyright")
        return BackendAvailability(backend_id=self.backend_id, available=bool(path), tool_path=path, tool_version=self.backend_version(), missing_deps=[] if path else ["pyright-langserver"], warnings=[] if path else ["Pyright unavailable; type/reference facts degraded"])

    def describe_capabilities(self) -> BackendCapabilityDescriptor:
        return BackendCapabilityDescriptor(backend_id=self.backend_id, backend_version=self.backend_version(), supported_node_types=[GraphNodeType.SAST_RULE], supported_edge_types=[GraphEdgeType.WARNED_BY, GraphEdgeType.CALLS], max_confidence=EvidenceStrength.STRUCTURED_REPOSITORY, derivation=DerivationType.ANALYSER, can_resolve_cross_file_calls=True, can_resolve_cross_module_calls=True, lsp_based=True, languages=["python"])

    def index_files(self, repo_root: Path, repo: RepoRef, snapshot: SnapshotRef, files: list[ScannedFile], *, run_id: str | None = None) -> BackendResult:
        result = BackendResult(backend_id=self.backend_id, backend_version=self.backend_version(), started_ts=_now_ts(), ended_ts=_now_ts())
        availability = self.check_availability()
        if not availability.available:
            result.diagnostics.append(IndexDiagnostic(diagnostic_id="diag:python.pyright:unavailable", severity=Severity.INFO, code="BACKEND_UNAVAILABLE", message="Pyright is unavailable; skipping LSP type/reference facts", details={"missing_deps": availability.missing_deps}))
        result.run_stats.files_scanned = len([file for file in files if file.language == "python"])
        result.run_stats.diagnostics_emitted = len(result.diagnostics)
        return result
