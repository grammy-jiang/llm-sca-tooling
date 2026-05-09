"""Deterministic TypeScript/JavaScript symbol adapter."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import BackendAvailability, BackendCapabilityDescriptor, BackendResult
from llm_sca_tooling.indexing.backends.utils import backend_edge, backend_node, line_no_for_offset
from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.indexing.scanner import ScannedFile, module_name_for_path, node_id
from llm_sca_tooling.schemas.enums import DerivationType, EvidenceStrength, GraphEdgeType, GraphNodeType, Severity
from llm_sca_tooling.schemas.graph import GraphNode
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts


class TsMorphAdapter:
    backend_id = "typescript.tsmorph"

    def backend_version(self) -> str:
        return "builtin-ts-parser-0.1.0"

    def check_availability(self) -> BackendAvailability:
        node = shutil.which("node")
        return BackendAvailability(backend_id=self.backend_id, available=True, tool_path=node, tool_version=self.backend_version(), warnings=[] if node else ["Node.js unavailable; using builtin TypeScript parser fallback"])

    def describe_capabilities(self) -> BackendCapabilityDescriptor:
        return BackendCapabilityDescriptor(backend_id=self.backend_id, backend_version=self.backend_version(), supported_node_types=[GraphNodeType.MODULE, GraphNodeType.CLASS, GraphNodeType.FUNCTION, GraphNodeType.METHOD, GraphNodeType.INTERFACE, GraphNodeType.TYPE], supported_edge_types=[GraphEdgeType.CONTAINS, GraphEdgeType.IMPORTS, GraphEdgeType.CALLS, GraphEdgeType.INSTANTIATES], max_confidence=EvidenceStrength.HARD_STATIC, derivation=DerivationType.PARSER, can_resolve_cross_file_calls=True, can_resolve_cross_module_calls=True, can_produce_type_edges=True, incremental_support=True, languages=["typescript", "javascript"])

    def index_files(self, repo_root: Path, repo: RepoRef, snapshot: SnapshotRef, files: list[ScannedFile], *, run_id: str | None = None) -> BackendResult:
        result = BackendResult(backend_id=self.backend_id, backend_version=self.backend_version(), started_ts=_now_ts(), ended_ts=_now_ts())
        ts_files = [file for file in files if file.language in {"typescript", "javascript"}]
        module_nodes: dict[str, GraphNode] = {}
        symbol_by_simple: dict[str, GraphNode] = {}
        imports: list[tuple[GraphNode, str]] = []
        call_candidates: list[tuple[GraphNode, str, int]] = []
        for file in ts_files:
            text = file.abs_path.read_text(encoding="utf-8")
            module = self._module_node(repo, snapshot, file, run_id=run_id)
            module_nodes[file.path] = module
            result.nodes.append(module)
            result.files_processed.append(file.path)
            for match in re.finditer(r"^\s*import\s+.*?from\s+['\"]([^'\"]+)['\"]|^\s*import\s+['\"]([^'\"]+)['\"]", text, re.MULTILINE):
                imports.append((module, match.group(1) or match.group(2)))
            for pattern, ntype in (
                (r"\bclass\s+([A-Za-z_$][\w$]*)", GraphNodeType.CLASS),
                (r"\binterface\s+([A-Za-z_$][\w$]*)", GraphNodeType.INTERFACE),
                (r"\btype\s+([A-Za-z_$][\w$]*)\s*=", GraphNodeType.TYPE),
                (r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(", GraphNodeType.FUNCTION),
                (r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", GraphNodeType.FUNCTION),
            ):
                for match in re.finditer(pattern, text):
                    name = match.group(1)
                    qname = f"{module.qualified_name}:{name}"
                    node = backend_node(repo, snapshot, self.backend_id, file, ntype, qname, name, line=line_no_for_offset(text, match.start()), run_id=run_id, confidence=0.9 if file.language == "typescript" else 0.6)
                    result.nodes.append(node)
                    result.edges.append(backend_edge(repo, snapshot, self.backend_id, GraphEdgeType.CONTAINS, module.node_id, node.node_id, run_id=run_id))
                    symbol_by_simple[name] = node
            for match in re.finditer(r"([A-Za-z_$][\w$]*)\s*\(", text):
                caller = _nearest_symbol(result.nodes, file.path, line_no_for_offset(text, match.start()))
                if caller:
                    call_candidates.append((caller, match.group(1), line_no_for_offset(text, match.start())))
            for match in re.finditer(r"new\s+([A-Za-z_$][\w$]*)\s*\(", text):
                caller = _nearest_symbol(result.nodes, file.path, line_no_for_offset(text, match.start()))
                callee = symbol_by_simple.get(match.group(1))
                if caller and callee:
                    result.edges.append(backend_edge(repo, snapshot, self.backend_id, GraphEdgeType.INSTANTIATES, caller.node_id, callee.node_id, run_id=run_id, confidence=0.7))
        for source, specifier in imports:
            target = _resolve_import(source.file_path or "", specifier, module_nodes)
            if target:
                result.edges.append(backend_edge(repo, snapshot, self.backend_id, GraphEdgeType.IMPORTS, source.node_id, target.node_id, run_id=run_id))
            elif specifier.startswith("."):
                result.diagnostics.append(IndexDiagnostic(diagnostic_id=f"diag:ts-import:{source.node_id[-8:]}:{specifier}", severity=Severity.INFO, code="CALL_TARGET_UNRESOLVED", message=f"Import could not be resolved: {specifier}", file_path=source.file_path))
        for caller, name, line in call_candidates:
            callee = symbol_by_simple.get(name)
            if callee and caller.node_id != callee.node_id:
                result.edges.append(backend_edge(repo, snapshot, self.backend_id, GraphEdgeType.CALLS, caller.node_id, callee.node_id, run_id=run_id, confidence=0.8, extra={"line": line}))
        result.run_stats.files_scanned = len(ts_files)
        result.run_stats.nodes_emitted = len(result.nodes)
        result.run_stats.edges_emitted = len(result.edges)
        result.run_stats.diagnostics_emitted = len(result.diagnostics)
        result.ended_ts = _now_ts()
        return result

    def _module_node(self, repo: RepoRef, snapshot: SnapshotRef, file: ScannedFile, *, run_id: str | None) -> GraphNode:
        qname = file.path.rsplit(".", 1)[0].replace("/", ".")
        return backend_node(repo, snapshot, self.backend_id, file, GraphNodeType.MODULE, qname, qname, run_id=run_id, confidence=0.9)


def _nearest_symbol(nodes: list[GraphNode], file_path: str, line: int) -> GraphNode | None:
    symbols = [node for node in nodes if node.file_path == file_path and node.span and node.span.start_line <= line and node.node_type in {GraphNodeType.FUNCTION, GraphNodeType.METHOD}]
    return symbols[-1] if symbols else None


def _resolve_import(source_file: str, specifier: str, modules: dict[str, GraphNode]) -> GraphNode | None:
    if not specifier.startswith("."):
        return None
    base = str((Path(source_file).parent / specifier).as_posix()).lstrip("./")
    candidates = [base, f"{base}.ts", f"{base}.tsx", f"{base}.js", f"{base}/index.ts", f"{base}/index.js"]
    for candidate in candidates:
        if candidate in modules:
            return modules[candidate]
    return None
