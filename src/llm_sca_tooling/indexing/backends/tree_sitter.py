"""Optional tree-sitter backend capability shim."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import BackendCapabilities, BackendResult
from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.schemas.enums import Severity
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts


class TreeSitterBackend:
    backend_id = "tree-sitter"

    def backend_version(self) -> str:
        return "available" if importlib.util.find_spec("tree_sitter") else "unavailable"

    def detect_capabilities(self) -> BackendCapabilities:
        installed = importlib.util.find_spec("tree_sitter") is not None
        return BackendCapabilities(
            backend_id=self.backend_id,
            installed=installed,
            version=self.backend_version(),
            supported_languages=["python"] if installed else [],
            supported_node_types=["module", "class", "function", "method"],
            supported_edge_types=["contains", "imports", "calls"],
            requires_external_binary=False,
            known_limitations=["Grammar package availability is environment-specific"],
        )

    def index_files(self, repo_root: Path, repo: RepoRef, snapshot: SnapshotRef, files: list[ScannedFile], *, run_id: str | None = None) -> BackendResult:
        now = _now_ts()
        result = BackendResult(backend_id=self.backend_id, backend_version=self.backend_version(), started_ts=now, ended_ts=now)
        if not self.detect_capabilities().installed:
            result.diagnostics.append(IndexDiagnostic(diagnostic_id="diag:tree-sitter:unavailable", severity=Severity.INFO, code="backend_unavailable", message="tree-sitter is not installed"))
        return result
