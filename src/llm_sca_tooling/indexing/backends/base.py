"""Backend interface and result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.diagnostics import IndexingDiagnostic
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef

__all__ = ["IndexingContext", "BackendCapabilities", "BackendResult", "IndexBackend"]


@dataclass
class IndexingContext:
    repo_root: Path
    repo_ref: RepoRef
    snapshot_ref: SnapshotRef
    config: IndexingConfig
    run_id: str


@dataclass
class BackendCapabilities:
    backend_id: str
    installed: bool
    version: str | None
    supported_languages: list[str]
    supported_node_types: list[str]
    requires_binary: bool = False
    limitations: list[str] = field(default_factory=list)


@dataclass
class BackendResult:
    backend_id: str
    backend_version: str | None
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    diagnostics: list[IndexingDiagnostic] = field(default_factory=list)
    files_processed: int = 0
    files_skipped: int = 0
    started_ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    ended_ts: str | None = None

    def finish(self) -> None:
        self.ended_ts = datetime.now(UTC).isoformat()


class IndexBackend(Protocol):
    """Protocol every indexing backend must implement."""

    @property
    def backend_id(self) -> str: ...

    def backend_version(self) -> str | None: ...

    def supported_languages(self) -> list[str]: ...

    async def detect_capabilities(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendCapabilities: ...

    async def index_files(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendResult: ...
