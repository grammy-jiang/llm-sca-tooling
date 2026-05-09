"""Optional Universal Ctags backend."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import BackendCapabilities, BackendResult
from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.indexing.scanner import ScannedFile, edge_id, node_id
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType, Severity
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef, SourceSpan
from llm_sca_tooling.storage.workspace import _now_ts


class CtagsBackend:
    backend_id = "ctags"

    def backend_version(self) -> str:
        binary = shutil.which("ctags") or shutil.which("universal-ctags")
        if not binary:
            return "unavailable"
        try:
            result = subprocess.run(
                [binary, "--version"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=5,
            )
        except OSError:
            return "unavailable"
        return result.stdout.splitlines()[0] if result.stdout else "unknown"

    def detect_capabilities(self) -> BackendCapabilities:
        installed = bool(shutil.which("ctags") or shutil.which("universal-ctags"))
        return BackendCapabilities(
            backend_id=self.backend_id,
            installed=installed,
            version=self.backend_version(),
            supported_languages=["python"] if installed else [],
            supported_node_types=["class", "function", "method", "variable"],
            supported_edge_types=["contains"],
            requires_external_binary=True,
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
        now = _now_ts()
        result = BackendResult(
            backend_id=self.backend_id,
            backend_version=self.backend_version(),
            started_ts=now,
            ended_ts=now,
        )
        if not self.detect_capabilities().installed:
            result.diagnostics.append(
                IndexDiagnostic(
                    diagnostic_id="diag:ctags:unavailable",
                    severity=Severity.INFO,
                    code="backend_unavailable",
                    message="ctags is not installed",
                )
            )
        return result


def parse_ctags_json_lines(
    lines: list[str],
    repo: RepoRef,
    snapshot: SnapshotRef,
    module_node: GraphNode,
    file_path: str,
    *,
    run_id: str | None = None,
) -> BackendResult:
    result = BackendResult(
        backend_id="ctags",
        backend_version="fixture",
        started_ts=_now_ts(),
        ended_ts=_now_ts(),
    )
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            result.diagnostics.append(
                IndexDiagnostic(
                    diagnostic_id="diag:ctags:json",
                    severity=Severity.WARNING,
                    code="ctags_json_parse_failed",
                    message=str(exc),
                    file_path=file_path,
                )
            )
            continue
        name = payload.get("name")
        kind = payload.get("kind")
        line_no = int(payload.get("line", 1))
        if not name:
            continue
        node_type = (
            GraphNodeType.CLASS
            if kind == "class"
            else (
                GraphNodeType.FUNCTION if kind == "function" else GraphNodeType.VARIABLE
            )
        )
        span = SourceSpan(file_path=file_path, start_line=line_no, end_line=line_no)
        provenance = make_provenance(
            source_tool="ctags",
            repo=repo,
            snapshot=snapshot,
            source_run_id=run_id,
            file=file_path,
            span=span,
        )
        node = GraphNode(
            node_id=node_id(
                repo.repo_id, snapshot, node_type, f"ctags:{file_path}:{name}:{line_no}"
            ),
            node_type=node_type,
            label=name,
            qualified_name=f"{module_node.qualified_name}:{name}",
            repo=repo,
            snapshot=snapshot,
            file_path=file_path,
            span=span,
            provenance=provenance,
            properties={"ctags_kind": kind},
            created_ts=_now_ts(),
        )
        result.nodes.append(node)
        result.edges.append(
            GraphEdge(
                edge_id=edge_id(
                    repo.repo_id,
                    snapshot,
                    GraphEdgeType.CONTAINS,
                    module_node.node_id,
                    node.node_id,
                ),
                edge_type=GraphEdgeType.CONTAINS,
                source_id=module_node.node_id,
                target_id=node.node_id,
                repo=repo,
                snapshot=snapshot,
                provenance=provenance,
                confidence=0.9,
                properties={},
                created_ts=_now_ts(),
            )
        )
    return result
