"""Unified TypeScript/JavaScript backend."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.backends.base import (
    BackendAvailability,
    BackendCapabilityDescriptor,
    BackendResult,
)
from llm_sca_tooling.indexing.backends.fact_reconciler import FactReconciler
from llm_sca_tooling.indexing.backends.typescript.madge_adapter import MadgeAdapter
from llm_sca_tooling.indexing.backends.typescript.package_meta import PackageMetadata
from llm_sca_tooling.indexing.backends.typescript.ts_test_detection import (
    detect_ts_test_runners,
)
from llm_sca_tooling.indexing.backends.typescript.tsmorph_adapter import TsMorphAdapter
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.schemas.enums import (
    DerivationType,
    EvidenceStrength,
    GraphEdgeType,
    GraphNodeType,
)
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts


class TypeScriptBackend:
    backend_id = "typescript.backend"

    def __init__(self) -> None:
        self.tsmorph = TsMorphAdapter()
        self.madge = MadgeAdapter()
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
                GraphNodeType.INTERFACE,
                GraphNodeType.TYPE,
            ],
            supported_edge_types=[
                GraphEdgeType.CONTAINS,
                GraphEdgeType.IMPORTS,
                GraphEdgeType.CALLS,
                GraphEdgeType.INSTANTIATES,
            ],
            max_confidence=EvidenceStrength.HARD_STATIC,
            derivation=DerivationType.PARSER,
            can_resolve_cross_file_calls=True,
            can_resolve_cross_module_calls=True,
            can_produce_type_edges=True,
            incremental_support=True,
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
        ts_result = self.tsmorph.index_files(
            repo_root, repo, snapshot, files, run_id=run_id
        )
        madge_result = self.madge.index_files(
            repo_root, repo, snapshot, files, run_id=run_id
        )
        reconciled = self.reconciler.reconcile([ts_result, madge_result])
        package_meta = PackageMetadata().parse(repo_root)
        runners = detect_ts_test_runners(repo_root, package_meta)
        result = BackendResult(
            backend_id=self.backend_id,
            backend_version=self.backend_version(),
            started_ts=ts_result.started_ts,
            ended_ts=_now_ts(),
        )
        result.nodes = reconciled.nodes
        result.edges = reconciled.edges
        result.diagnostics = [
            *ts_result.diagnostics,
            *madge_result.diagnostics,
            *reconciled.diagnostics,
        ]
        result.files_processed = sorted(
            set(ts_result.files_processed + madge_result.files_processed)
        )
        result.capabilities_used = [
            "typescript.tsmorph",
            "typescript.madge",
            "typescript.package_meta",
        ]
        result.run_stats.files_scanned = len(
            [file for file in files if file.language in {"typescript", "javascript"}]
        )
        result.run_stats.nodes_emitted = len(result.nodes)
        result.run_stats.edges_emitted = len(result.edges)
        result.run_stats.diagnostics_emitted = len(result.diagnostics)
        result.output_hash = str(hash(str(package_meta) + str(runners)))
        return result
