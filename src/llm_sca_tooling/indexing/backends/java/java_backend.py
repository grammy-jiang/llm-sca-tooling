"""Capability-gated Java backend."""

from __future__ import annotations

import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import (
    BackendCapabilities,
    BackendResult,
    IndexingContext,
)
from llm_sca_tooling.indexing.backends.capability import (
    BackendAvailability,
    BackendCapabilityDescriptor,
)
from llm_sca_tooling.indexing.backends.java.capability import java_backend_enabled
from llm_sca_tooling.indexing.hashing import make_edge_id, make_node_id
from llm_sca_tooling.indexing.provenance import parser_provenance
from llm_sca_tooling.schemas.graph import (
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
)
from llm_sca_tooling.schemas.provenance import DerivationType, SourceSpan

__all__ = ["JavaBackend"]

_CLASS_RE = re.compile(r"\b(?:public\s+)?(?:final\s+)?class\s+([A-Za-z_]\w*)")
_METHOD_RE = re.compile(
    r"\b(?:public|private|protected)?\s*(?:static\s+)?"
    r"[A-Za-z_]\w*(?:<[^>]+>)?\s+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{"
)
_IMPORT_RE = re.compile(r"^\s*import\s+([\w.]+);", re.MULTILINE)
_CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")


def _now() -> str:
    return datetime.now(UTC).isoformat()


class JavaBackend:
    @property
    def backend_id(self) -> str:
        return "java.jdt"

    def backend_version(self) -> str:
        return "phase5-stub"

    def supported_languages(self) -> list[str]:
        return ["java"]

    def describe_capabilities(self) -> BackendCapabilityDescriptor:
        return BackendCapabilityDescriptor(
            backend_id=self.backend_id,
            backend_version=self.backend_version(),
            supported_node_types=[GraphNodeType.class_, GraphNodeType.method],
            supported_edge_types=[GraphEdgeType.imports, GraphEdgeType.calls],
            max_confidence="heuristic",
            derivation=DerivationType.analyser,
            can_resolve_cross_file_calls=False,
            can_resolve_cross_module_calls=False,
            can_produce_type_edges=False,
            can_produce_nullness_edges=False,
            can_produce_dataflow_edges=False,
            can_index_generated_files=False,
            requires_compile_commands=False,
            requires_build_artifacts=True,
            incremental_support=False,
            lsp_based=False,
            languages=self.supported_languages(),
        )

    async def check_availability(
        self, context: IndexingContext | None = None
    ) -> BackendAvailability:
        if not java_backend_enabled():
            return BackendAvailability(
                backend_id=self.backend_id,
                available=False,
                missing_deps=["JAVA_BACKEND_ENABLED"],
                warnings=["Java backend disabled by default"],
            )
        tool = shutil.which("javac") or shutil.which("java")
        return BackendAvailability(
            backend_id=self.backend_id,
            available=bool(tool),
            tool_path=tool,
            tool_version=self.backend_version(),
            missing_deps=[] if tool else ["javac"],
        )

    async def detect_capabilities(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendCapabilities:
        availability = await self.check_availability(context)
        return BackendCapabilities(
            backend_id=self.backend_id,
            installed=availability.available,
            version=self.backend_version(),
            supported_languages=self.supported_languages(),
            supported_node_types=[
                node_type.value
                for node_type in self.describe_capabilities().supported_node_types
            ],
            requires_binary=True,
            limitations=[] if availability.available else availability.missing_deps,
        )

    async def index_files(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendResult:
        result = BackendResult(self.backend_id, self.backend_version())
        if not java_backend_enabled():
            result.finish()
            return result

        java_files = [path for path in files if path.suffix == ".java"]
        method_nodes: dict[str, str] = {}
        for path in java_files:
            rel = str(path.relative_to(context.repo_root)).replace("\\", "/")
            text = path.read_text(errors="replace")
            file_id = make_node_id(context.repo_ref.repo_id, "module", rel)
            result.nodes.append(
                _node(context, file_id, GraphNodeType.module, Path(rel).stem, rel, rel)
            )
            for import_name in _IMPORT_RE.findall(text):
                target_id = make_node_id(
                    context.repo_ref.repo_id, "package", import_name
                )
                result.nodes.append(
                    _node(
                        context,
                        target_id,
                        GraphNodeType.package,
                        import_name.rsplit(".", 1)[-1],
                        import_name,
                        rel,
                    )
                )
                result.edges.append(
                    _edge(context, GraphEdgeType.imports, file_id, target_id, rel)
                )

            class_node = file_id
            for class_match in _CLASS_RE.finditer(text):
                name = class_match.group(1)
                node_id = make_node_id(
                    context.repo_ref.repo_id, "class", f"{rel}::{name}"
                )
                class_node = node_id
                result.nodes.append(
                    _node(
                        context,
                        node_id,
                        GraphNodeType.class_,
                        name,
                        name,
                        rel,
                        _span(rel, text, class_match.start()),
                    )
                )
                result.edges.append(
                    _edge(context, GraphEdgeType.contains, file_id, node_id, rel)
                )

            for method_match in _METHOD_RE.finditer(text):
                name = method_match.group(1)
                node_id = make_node_id(
                    context.repo_ref.repo_id, "method", f"{rel}::{name}"
                )
                method_nodes[f"{rel}::{name}"] = node_id
                result.nodes.append(
                    _node(
                        context,
                        node_id,
                        GraphNodeType.method,
                        name,
                        name,
                        rel,
                        _span(rel, text, method_match.start()),
                    )
                )
                result.edges.append(
                    _edge(context, GraphEdgeType.contains, class_node, node_id, rel)
                )
            result.files_processed += 1

        for path in java_files:
            rel = str(path.relative_to(context.repo_root)).replace("\\", "/")
            text = path.read_text(errors="replace")
            for call_match in _CALL_RE.finditer(text):
                caller = _enclosing_method(text, method_nodes, rel, call_match.start())
                callee = method_nodes.get(f"{rel}::{call_match.group(1)}")
                if caller and callee and callee != caller:
                    result.edges.append(
                        _edge(context, GraphEdgeType.calls, caller, callee, rel)
                    )

        result.finish()
        return result


def _node(
    context: IndexingContext,
    node_id: str,
    node_type: GraphNodeType,
    label: str,
    qualified_name: str,
    file_path: str,
    span: SourceSpan | None = None,
) -> GraphNode:
    return GraphNode(
        node_id=node_id,
        node_type=node_type,
        label=label,
        qualified_name=qualified_name,
        repo=context.repo_ref,
        snapshot=context.snapshot_ref,
        file_path=file_path,
        span=span,
        provenance=parser_provenance(
            context.repo_ref,
            context.snapshot_ref,
            "java.jdt",
            file=file_path,
            span=span,
            confidence=0.7,
        ),
        properties={"language": "java"},
        created_ts=_now(),
    )


def _edge(
    context: IndexingContext,
    edge_type: GraphEdgeType,
    source_id: str,
    target_id: str,
    file_path: str,
) -> GraphEdge:
    return GraphEdge(
        edge_id=make_edge_id(
            context.repo_ref.repo_id, edge_type.value, source_id, target_id
        ),
        edge_type=edge_type,
        source_id=source_id,
        target_id=target_id,
        repo=context.repo_ref,
        snapshot=context.snapshot_ref,
        provenance=parser_provenance(
            context.repo_ref,
            context.snapshot_ref,
            "java.jdt",
            file=file_path,
            confidence=0.7,
        ),
        confidence=0.7,
        properties={"agreement": "candidate"},
        created_ts=_now(),
    )


def _span(file_path: str, text: str, offset: int) -> SourceSpan:
    line = text[:offset].count("\n") + 1
    return SourceSpan(file_path=file_path, start_line=line, end_line=line)


def _enclosing_method(
    text: str, symbols: dict[str, str], rel: str, offset: int
) -> str | None:
    current: str | None = None
    for match in _METHOD_RE.finditer(text):
        if match.start() > offset:
            break
        node_id = symbols.get(f"{rel}::{match.group(1)}")
        if node_id:
            current = node_id
    return current
