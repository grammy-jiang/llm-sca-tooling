"""libclang-style C/C++ parser adapter with deterministic fallback."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import (
    BackendAvailability,
    BackendCapabilityDescriptor,
    BackendResult,
)
from llm_sca_tooling.indexing.backends.cpp.compile_commands import CompileCommand
from llm_sca_tooling.indexing.backends.utils import (
    backend_edge,
    backend_node,
    line_no_for_offset,
)
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


class LibclangAdapter:
    backend_id = "cpp.libclang"

    def backend_version(self) -> str:
        return "builtin-cpp-parser-0.1.0"

    def check_availability(self) -> BackendAvailability:
        clang = shutil.which("clang") or shutil.which("clang++")
        return BackendAvailability(
            backend_id=self.backend_id,
            available=True,
            tool_path=clang,
            tool_version=self.backend_version(),
            warnings=(
                []
                if clang
                else ["libclang/clang unavailable; using builtin C/C++ parser fallback"]
            ),
        )

    def describe_capabilities(self) -> BackendCapabilityDescriptor:
        return BackendCapabilityDescriptor(
            backend_id=self.backend_id,
            backend_version=self.backend_version(),
            supported_node_types=[
                GraphNodeType.CLASS,
                GraphNodeType.FUNCTION,
                GraphNodeType.METHOD,
                GraphNodeType.VARIABLE,
            ],
            supported_edge_types=[
                GraphEdgeType.CONTAINS,
                GraphEdgeType.IMPORTS,
                GraphEdgeType.CALLS,
                GraphEdgeType.OWNS,
                GraphEdgeType.INSTANTIATES,
            ],
            max_confidence=EvidenceStrength.HARD_STATIC,
            derivation=DerivationType.PARSER,
            can_resolve_cross_file_calls=True,
            requires_compile_commands=True,
            incremental_support=True,
            languages=["c", "cpp"],
        )

    def index_files(
        self,
        repo_root: Path,
        repo: RepoRef,
        snapshot: SnapshotRef,
        files: list[ScannedFile],
        compile_commands: list[CompileCommand],
        *,
        run_id: str | None = None,
    ) -> BackendResult:
        result = BackendResult(
            backend_id=self.backend_id,
            backend_version=self.backend_version(),
            started_ts=_now_ts(),
            ended_ts=_now_ts(),
        )
        listed = {command.repo_relative_file for command in compile_commands}
        symbol_by_name: dict[str, GraphNode] = {}
        call_candidates: list[tuple[GraphNode, str, int]] = []
        cpp_files = [file for file in files if file.language in {"c", "cpp"}]
        for file in cpp_files:
            text = file.abs_path.read_text(encoding="utf-8")
            if (
                compile_commands
                and file.path not in listed
                and file.abs_path.suffix.lower() not in {".h", ".hpp", ".hh", ".hxx"}
            ):
                result.diagnostics.append(
                    IndexDiagnostic(
                        diagnostic_id=f"diag:cpp-coverage:{file.sha256[:8]}",
                        severity=Severity.INFO,
                        code="BACKEND_DEGRADED",
                        message="File missing from compile_commands.json",
                        file_path=file.path,
                    )
                )
            file_node = backend_node(
                repo,
                snapshot,
                self.backend_id,
                file,
                GraphNodeType.MODULE,
                file.path.replace("/", "."),
                file.path,
                run_id=run_id,
                confidence=0.8,
            )
            result.nodes.append(file_node)
            for include in re.finditer(
                r"^\s*#\s*include\s+[<\"]([^>\"]+)[>\"]", text, re.MULTILINE
            ):
                target = _resolve_include(
                    include.group(1), file.path, {item.path: item for item in cpp_files}
                )
                if target:
                    target_node = backend_node(
                        repo,
                        snapshot,
                        self.backend_id,
                        target,
                        GraphNodeType.MODULE,
                        target.path.replace("/", "."),
                        target.path,
                        run_id=run_id,
                        confidence=0.8,
                    )
                    result.nodes.append(target_node)
                    result.edges.append(
                        backend_edge(
                            repo,
                            snapshot,
                            self.backend_id,
                            GraphEdgeType.IMPORTS,
                            file_node.node_id,
                            target_node.node_id,
                            run_id=run_id,
                        )
                    )
            for match in re.finditer(r"\b(?:class|struct)\s+([A-Za-z_]\w*)", text):
                node = backend_node(
                    repo,
                    snapshot,
                    self.backend_id,
                    file,
                    GraphNodeType.CLASS,
                    f"{file.path}:{match.group(1)}",
                    match.group(1),
                    line=line_no_for_offset(text, match.start()),
                    run_id=run_id,
                )
                result.nodes.append(node)
                result.edges.append(
                    backend_edge(
                        repo,
                        snapshot,
                        self.backend_id,
                        GraphEdgeType.CONTAINS,
                        file_node.node_id,
                        node.node_id,
                        run_id=run_id,
                    )
                )
                symbol_by_name[match.group(1)] = node
            for match in re.finditer(
                r"\b(?:[A-Za-z_]\w*::)?([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?:\{|;)",
                text,
            ):
                name = match.group(2)
                if name in {"if", "for", "while", "switch"}:
                    continue
                node = backend_node(
                    repo,
                    snapshot,
                    self.backend_id,
                    file,
                    GraphNodeType.FUNCTION,
                    f"{file.path}:{name}",
                    name,
                    line=line_no_for_offset(text, match.start()),
                    run_id=run_id,
                )
                result.nodes.append(node)
                result.edges.append(
                    backend_edge(
                        repo,
                        snapshot,
                        self.backend_id,
                        GraphEdgeType.CONTAINS,
                        file_node.node_id,
                        node.node_id,
                        run_id=run_id,
                    )
                )
                symbol_by_name[name] = node
            for match in re.finditer(r"([A-Za-z_]\w*)\s*\(", text):
                caller = _nearest(
                    result.nodes, file.path, line_no_for_offset(text, match.start())
                )
                if caller:
                    call_candidates.append(
                        (
                            caller,
                            match.group(1),
                            line_no_for_offset(text, match.start()),
                        )
                    )
            result.files_processed.append(file.path)
        for caller, name, line in call_candidates:
            callee = symbol_by_name.get(name)
            if callee and caller.node_id != callee.node_id:
                result.edges.append(
                    backend_edge(
                        repo,
                        snapshot,
                        self.backend_id,
                        GraphEdgeType.CALLS,
                        caller.node_id,
                        callee.node_id,
                        run_id=run_id,
                        confidence=0.7,
                        extra={"line": line},
                    )
                )
        result.run_stats.files_scanned = len(cpp_files)
        result.run_stats.nodes_emitted = len(result.nodes)
        result.run_stats.edges_emitted = len(result.edges)
        result.run_stats.diagnostics_emitted = len(result.diagnostics)
        result.ended_ts = _now_ts()
        return result


def _nearest(nodes: list[GraphNode], file_path: str, line: int) -> GraphNode | None:
    symbols = [
        node
        for node in nodes
        if node.file_path == file_path
        and node.span
        and node.span.start_line <= line
        and node.node_type == GraphNodeType.FUNCTION
    ]
    return symbols[-1] if symbols else None


def _resolve_include(
    include: str, source_path: str, files: dict[str, ScannedFile]
) -> ScannedFile | None:
    candidates = [
        str((Path(source_path).parent / include).as_posix()).lstrip("./"),
        include,
    ]
    for candidate in candidates:
        if candidate in files:
            return files[candidate]
    return None
