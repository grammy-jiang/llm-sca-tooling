"""Indexing result model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from llm_sca_tooling.indexing.diagnostics import IndexingDiagnostic

__all__ = ["IndexingResult"]


@dataclass
class IndexingResult:
    """Summary of a completed graph build or update run."""

    repo_id: str
    run_id: str
    snapshot_id: str
    status: str  # fresh | partial | failed | stale | unknown
    files_scanned: int = 0
    files_indexed: int = 0
    files_skipped: int = 0
    nodes_added: int = 0
    edges_added: int = 0
    diagnostics: list[IndexingDiagnostic] = field(default_factory=list)
    graph_manifest_id: str | None = None
    artifact_refs: list[str] = field(default_factory=list)
    stale_summary_count: int = 0
    backend_versions: dict[str, str] = field(default_factory=dict)
    started_ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    ended_ts: str | None = None

    def finish(self, status: str | None = None) -> None:
        self.status = status or self.status
        self.ended_ts = datetime.now(UTC).isoformat()

    @property
    def errors(self) -> list[IndexingDiagnostic]:
        from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity

        return [d for d in self.diagnostics if d.severity == DiagnosticSeverity.error]

    @property
    def warnings(self) -> list[IndexingDiagnostic]:
        from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity

        return [d for d in self.diagnostics if d.severity == DiagnosticSeverity.warning]
