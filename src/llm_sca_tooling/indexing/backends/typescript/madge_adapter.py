"""madge-style dependency graph adapter."""

from __future__ import annotations

import shutil
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import (
    BackendAvailability,
    BackendCapabilityDescriptor,
    BackendResult,
)
from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.schemas.enums import (
    DerivationType,
    EvidenceStrength,
    GraphEdgeType,
    Severity,
)
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts


class MadgeAdapter:
    backend_id = "typescript.madge"

    def backend_version(self) -> str:
        return "dependency-check-0.1.0"

    def check_availability(self) -> BackendAvailability:
        return BackendAvailability(
            backend_id=self.backend_id,
            available=True,
            tool_path=shutil.which("madge"),
            tool_version=self.backend_version(),
            warnings=(
                []
                if shutil.which("madge")
                else ["madge unavailable; dependency cross-check limited"]
            ),
        )

    def describe_capabilities(self) -> BackendCapabilityDescriptor:
        return BackendCapabilityDescriptor(
            backend_id=self.backend_id,
            backend_version=self.backend_version(),
            supported_edge_types=[GraphEdgeType.IMPORTS],
            max_confidence=EvidenceStrength.STRUCTURED_REPOSITORY,
            derivation=DerivationType.ANALYSER,
            can_resolve_cross_module_calls=False,
            incremental_support=False,
            languages=["typescript", "javascript"],
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
        result.files_processed = [
            file.path for file in files if file.language in {"typescript", "javascript"}
        ]
        result.diagnostics.append(
            IndexDiagnostic(
                diagnostic_id="diag:typescript.madge:degraded",
                severity=Severity.INFO,
                code="BACKEND_DEGRADED",
                message="madge dependency graph is represented by ts-morph import facts in this deterministic environment",
            )
        )
        return result
