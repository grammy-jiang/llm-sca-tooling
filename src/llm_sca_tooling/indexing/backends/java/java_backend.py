"""Optional Java backend stub."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.backends.base import (
    BackendAvailability,
    BackendCapabilityDescriptor,
    BackendResult,
)
from llm_sca_tooling.indexing.backends.java.capability import JAVA_BACKEND_ENABLED
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.schemas.enums import (
    DerivationType,
    EvidenceStrength,
    GraphEdgeType,
    GraphNodeType,
)
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts


class JavaBackend:
    backend_id = "java.jdt"

    def backend_version(self) -> str:
        return "0.1.0"

    def check_availability(self) -> BackendAvailability:
        return BackendAvailability(
            backend_id=self.backend_id,
            available=JAVA_BACKEND_ENABLED,
            tool_version=self.backend_version(),
            missing_deps=[] if JAVA_BACKEND_ENABLED else ["java_backend_disabled"],
        )

    def describe_capabilities(self) -> BackendCapabilityDescriptor:
        return BackendCapabilityDescriptor(
            backend_id=self.backend_id,
            backend_version=self.backend_version(),
            supported_node_types=[GraphNodeType.CLASS, GraphNodeType.METHOD],
            supported_edge_types=[GraphEdgeType.IMPORTS, GraphEdgeType.CALLS],
            max_confidence=EvidenceStrength.STRUCTURED_REPOSITORY,
            derivation=DerivationType.ANALYSER,
            languages=["java"],
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
        return BackendResult(
            backend_id=self.backend_id,
            backend_version=self.backend_version(),
            started_ts=_now_ts(),
            ended_ts=_now_ts(),
        )
