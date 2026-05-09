"""pyan3-style Python call graph adapter."""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import (
    BackendAvailability,
    BackendCapabilityDescriptor,
    BackendResult,
)
from llm_sca_tooling.indexing.backends.python_ast import module_name_for_path
from llm_sca_tooling.indexing.backends.utils import backend_edge
from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.schemas.enums import (
    DerivationType,
    EvidenceStrength,
    GraphEdgeType,
    GraphNodeType,
    Severity,
)
from llm_sca_tooling.schemas.graph import GraphNode
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts


class Pyan3Adapter:
    backend_id = "python.pyan3"

    def backend_version(self) -> str:
        return "builtin-static-0.1.0"

    def check_availability(self) -> BackendAvailability:
        return BackendAvailability(
            backend_id=self.backend_id,
            available=True,
            tool_path=shutil.which("pyan3"),
            tool_version=self.backend_version(),
            warnings=(
                []
                if shutil.which("pyan3")
                else ["pyan3 CLI unavailable; using builtin AST call extractor"]
            ),
        )

    def describe_capabilities(self) -> BackendCapabilityDescriptor:
        return BackendCapabilityDescriptor(
            backend_id=self.backend_id,
            backend_version=self.backend_version(),
            supported_edge_types=[GraphEdgeType.CALLS],
            max_confidence=EvidenceStrength.STRUCTURED_REPOSITORY,
            derivation=DerivationType.ANALYSER,
            can_resolve_cross_file_calls=True,
            can_resolve_cross_module_calls=True,
            incremental_support=False,
            languages=["python"],
        )

    def index_files(
        self,
        repo_root: Path,
        repo: RepoRef,
        snapshot: SnapshotRef,
        files: list[ScannedFile],
        ast_nodes: list[GraphNode],
        *,
        run_id: str | None = None,
    ) -> BackendResult:
        result = BackendResult(
            backend_id=self.backend_id,
            backend_version=self.backend_version(),
            started_ts=_now_ts(),
            ended_ts=_now_ts(),
            capabilities_used=["builtin-ast-call-extractor"],
        )
        by_name = {
            node.qualified_name: node for node in ast_nodes if node.qualified_name
        }
        by_simple = {
            node.qualified_name.rsplit(":", 1)[-1].split(".")[-1]: node
            for node in ast_nodes
            if node.qualified_name
            and node.node_type in {GraphNodeType.FUNCTION, GraphNodeType.METHOD}
        }
        for file in [item for item in files if item.language == "python"]:
            try:
                tree = ast.parse(file.abs_path.read_text(encoding="utf-8"))
            except SyntaxError as exc:
                result.diagnostics.append(
                    IndexDiagnostic(
                        diagnostic_id=f"diag:pyan3:{file.sha256[:12]}",
                        severity=Severity.WARNING,
                        code="FILE_PARSE_ERROR",
                        message=str(exc),
                        file_path=file.path,
                    )
                )
                result.files_skipped.append(file.path)
                continue
            module = module_name_for_path(file.path)
            current_functions = [
                node
                for node in by_name.values()
                if node.qualified_name and node.qualified_name.startswith(f"{module}:")
            ]
            for call in [node for node in ast.walk(tree) if isinstance(node, ast.Call)]:
                callee_name = _call_name(call)
                caller = _enclosing(call, current_functions)
                callee = by_simple.get(callee_name or "")
                if caller and callee and caller.node_id != callee.node_id:
                    result.edges.append(
                        backend_edge(
                            repo,
                            snapshot,
                            self.backend_id,
                            GraphEdgeType.CALLS,
                            caller.node_id,
                            callee.node_id,
                            run_id=run_id,
                            derivation=DerivationType.ANALYSER,
                            evidence_strength=EvidenceStrength.STRUCTURED_REPOSITORY,
                            confidence=0.7,
                        )
                    )
                elif caller:
                    result.diagnostics.append(
                        IndexDiagnostic(
                            diagnostic_id=f"diag:pyan3-unresolved:{file.sha256[:8]}:{getattr(call, 'lineno', 0)}",
                            severity=Severity.INFO,
                            code="CALL_TARGET_UNRESOLVED",
                            message="Call target could not be resolved",
                            file_path=file.path,
                        )
                    )
            result.files_processed.append(file.path)
        result.run_stats.nodes_emitted = len(result.nodes)
        result.run_stats.edges_emitted = len(result.edges)
        result.run_stats.diagnostics_emitted = len(result.diagnostics)
        result.ended_ts = _now_ts()
        return result


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _enclosing(call: ast.Call, symbols: list[GraphNode]) -> GraphNode | None:
    line = getattr(call, "lineno", 0)
    candidates = [
        symbol
        for symbol in symbols
        if symbol.span
        and symbol.span.start_line <= line <= symbol.span.end_line
        and symbol.node_type in {GraphNodeType.FUNCTION, GraphNodeType.METHOD}
    ]
    return (
        sorted(
            candidates,
            key=lambda symbol: (
                symbol.span.end_line - symbol.span.start_line if symbol.span else 9999
            ),
        )[0]
        if candidates
        else None
    )
