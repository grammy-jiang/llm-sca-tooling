"""Pyright availability and diagnostic adapter."""

from __future__ import annotations

import shutil
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import (
    BackendAvailability,
    BackendCapabilityDescriptor,
    BackendResult,
)
from llm_sca_tooling.indexing.backends.utils import backend_edge, backend_node
from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.indexing.lsp.client import LspClient
from llm_sca_tooling.indexing.lsp.errors import LspCrash, LspTimeout
from llm_sca_tooling.indexing.scanner import ScannedFile, node_id
from llm_sca_tooling.schemas.enums import (
    DerivationType,
    EvidenceStrength,
    GraphEdgeType,
    GraphNodeType,
    Severity,
)
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts


class PyrightAdapter:
    backend_id = "python.pyright"

    def __init__(
        self, command: list[str] | None = None, *, diagnostic_timeout_ms: int = 1000
    ) -> None:
        self.command = command
        self.diagnostic_timeout_ms = diagnostic_timeout_ms

    def backend_version(self) -> str:
        return "pyright-lsp-adapter-0.2.0"

    def check_availability(self) -> BackendAvailability:
        if self.command:
            return BackendAvailability(
                backend_id=self.backend_id,
                available=True,
                tool_path=self.command[0],
                tool_version=self.backend_version(),
            )
        path = shutil.which("pyright-langserver")
        return BackendAvailability(
            backend_id=self.backend_id,
            available=bool(path),
            tool_path=path,
            tool_version=self.backend_version(),
            missing_deps=[] if path else ["pyright-langserver"],
            warnings=(
                [] if path else ["Pyright unavailable; type/reference facts degraded"]
            ),
        )

    def describe_capabilities(self) -> BackendCapabilityDescriptor:
        return BackendCapabilityDescriptor(
            backend_id=self.backend_id,
            backend_version=self.backend_version(),
            supported_node_types=[GraphNodeType.SAST_RULE],
            supported_edge_types=[GraphEdgeType.WARNED_BY, GraphEdgeType.CALLS],
            max_confidence=EvidenceStrength.STRUCTURED_REPOSITORY,
            derivation=DerivationType.ANALYSER,
            can_resolve_cross_file_calls=True,
            can_resolve_cross_module_calls=True,
            lsp_based=True,
            languages=["python"],
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
        result = BackendResult(
            backend_id=self.backend_id,
            backend_version=self.backend_version(),
            started_ts=_now_ts(),
            ended_ts=_now_ts(),
        )
        availability = self.check_availability()
        python_files = [file for file in files if file.language == "python"]
        if not availability.available:
            result.diagnostics.append(
                IndexDiagnostic(
                    diagnostic_id="diag:python.pyright:unavailable",
                    severity=Severity.INFO,
                    code="BACKEND_UNAVAILABLE",
                    message="Pyright is unavailable; skipping LSP type/reference facts",
                    details={"missing_deps": availability.missing_deps},
                )
            )
            result.run_stats.files_scanned = len(python_files)
            result.run_stats.diagnostics_emitted = len(result.diagnostics)
            return result
        if not python_files:
            return result
        client = LspClient(
            self.backend_id,
            self.command or [availability.tool_path or "pyright-langserver", "--stdio"],
            repo_root,
        )
        try:
            client.start()
            for file in python_files:
                uri = (repo_root / file.path).as_uri()
                client.open_document(
                    uri, "python", (repo_root / file.path).read_text(encoding="utf-8")
                )
                notification = client.wait_for_notification(
                    "textDocument/publishDiagnostics",
                    timeout_ms=self.diagnostic_timeout_ms,
                )
                if notification:
                    self._append_lsp_diagnostics(
                        result,
                        repo,
                        snapshot,
                        file,
                        notification.get("params", {}).get("diagnostics", []),
                        run_id=run_id,
                    )
                client.close_document(uri)
                result.files_processed.append(file.path)
        except (OSError, LspCrash, LspTimeout) as exc:
            result.diagnostics.append(
                IndexDiagnostic(
                    diagnostic_id="diag:python.pyright:lsp_failure",
                    severity=Severity.ERROR,
                    code="LSP_FAILURE",
                    message=f"Pyright LSP failed: {exc}",
                    details={"exception": exc.__class__.__name__},
                )
            )
            result.files_skipped.extend(
                [
                    file.path
                    for file in python_files
                    if file.path not in result.files_processed
                ]
            )
        finally:
            client.stop()
            result.ended_ts = _now_ts()
        result.run_stats.files_scanned = len(python_files)
        result.run_stats.files_failed = len(result.files_skipped)
        result.run_stats.nodes_emitted = len(result.nodes)
        result.run_stats.edges_emitted = len(result.edges)
        result.run_stats.diagnostics_emitted = len(result.diagnostics)
        return result

    def _append_lsp_diagnostics(
        self,
        result: BackendResult,
        repo: RepoRef,
        snapshot: SnapshotRef,
        file: ScannedFile,
        diagnostics: list[dict],
        *,
        run_id: str | None,
    ) -> None:
        for index, diagnostic in enumerate(diagnostics):
            severity = _severity(diagnostic.get("severity"))
            start = diagnostic.get("range", {}).get("start", {})
            line = int(start.get("line", 0)) + 1
            code = str(diagnostic.get("code") or "PYRIGHT_DIAGNOSTIC")
            message = str(diagnostic.get("message") or code)
            diagnostic_id = f"diag:python.pyright:{file.path}:{line}:{index}"
            result.diagnostics.append(
                IndexDiagnostic(
                    diagnostic_id=diagnostic_id,
                    severity=severity,
                    code=code,
                    message=message,
                    file_path=file.path,
                    details={
                        "source": diagnostic.get("source", "pyright"),
                        "lsp_code": code,
                        "start_line": line,
                        "end_line": line,
                    },
                )
            )
            diagnostic_node = backend_node(
                repo,
                snapshot,
                self.backend_id,
                file,
                GraphNodeType.SAST_RULE,
                f"{code}:{file.path}:{line}:{index}",
                code,
                line=line,
                run_id=run_id,
                derivation=DerivationType.ANALYSER,
                evidence_strength=EvidenceStrength.STRUCTURED_REPOSITORY,
                confidence=0.75,
                extra={"message": message, "severity": severity.value},
            )
            result.nodes.append(diagnostic_node)
            file_node_id = node_id(
                repo.repo_id, snapshot, GraphNodeType.FILE, file.path
            )
            result.edges.append(
                backend_edge(
                    repo,
                    snapshot,
                    self.backend_id,
                    GraphEdgeType.WARNED_BY,
                    diagnostic_node.node_id,
                    file_node_id,
                    run_id=run_id,
                    derivation=DerivationType.ANALYSER,
                    evidence_strength=EvidenceStrength.STRUCTURED_REPOSITORY,
                    confidence=0.75,
                    extra={"diagnostic_id": diagnostic_id},
                )
            )


def _severity(value: object) -> Severity:
    if value == 1:
        return Severity.ERROR
    if value == 2:
        return Severity.WARNING
    if value == 4:
        return Severity.NOTE
    return Severity.INFO
