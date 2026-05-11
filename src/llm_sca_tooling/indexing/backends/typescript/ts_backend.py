"""Pure-Python TypeScript/JavaScript backend used when Node adapters are unavailable."""

from __future__ import annotations

import re
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
from llm_sca_tooling.indexing.backends.typescript.package_meta import (
    read_package_metadata,
)
from llm_sca_tooling.indexing.backends.typescript.ts_test_detection import (
    detect_test_runners,
)
from llm_sca_tooling.indexing.hashing import make_edge_id, make_node_id
from llm_sca_tooling.indexing.provenance import make_provenance, parser_provenance
from llm_sca_tooling.schemas.graph import (
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
)
from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    EvidenceStrength,
    SourceSpan,
)

__all__ = ["TypeScriptBackend"]

_BACKEND_ID = "typescript.tsmorph"
_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}
_FUNC_RE = re.compile(r"(?:export\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")
_CLASS_RE = re.compile(r"(?:export\s+)?class\s+([A-Za-z_$][\w$]*)")
_INTERFACE_RE = re.compile(r"(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)")
_IMPORT_RE = re.compile(r"import\s+(?:[^'\"]+\s+from\s+)?['\"]([^'\"]+)['\"]")
_CALL_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")


def _now() -> str:
    return datetime.now(UTC).isoformat()


class TypeScriptBackend:
    @property
    def backend_id(self) -> str:
        return _BACKEND_ID

    def backend_version(self) -> str:
        return "phase5-python-fallback"

    def supported_languages(self) -> list[str]:
        return ["javascript", "typescript"]

    def describe_capabilities(self) -> BackendCapabilityDescriptor:
        return BackendCapabilityDescriptor(
            backend_id=_BACKEND_ID,
            backend_version=self.backend_version(),
            supported_node_types=[
                GraphNodeType.module,
                GraphNodeType.class_,
                GraphNodeType.function,
                GraphNodeType.interface,
                GraphNodeType.build_target,
                GraphNodeType.ci_job,
            ],
            supported_edge_types=[
                GraphEdgeType.contains,
                GraphEdgeType.imports,
                GraphEdgeType.calls,
            ],
            max_confidence="heuristic",
            derivation=DerivationType.heuristic,
            can_resolve_cross_file_calls=False,
            can_resolve_cross_module_calls=True,
            can_produce_type_edges=True,
            can_produce_nullness_edges=False,
            can_produce_dataflow_edges=False,
            can_index_generated_files=False,
            requires_compile_commands=False,
            requires_build_artifacts=False,
            incremental_support=True,
            lsp_based=False,
            languages=self.supported_languages(),
        )

    async def check_availability(
        self, context: IndexingContext | None = None
    ) -> BackendAvailability:
        return BackendAvailability(
            backend_id=_BACKEND_ID,
            available=True,
            tool_version=self.backend_version(),
            warnings=["ts-morph Node runner unavailable; using Python fallback"],
        )

    async def detect_capabilities(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendCapabilities:
        return BackendCapabilities(
            backend_id=_BACKEND_ID,
            installed=True,
            version=self.backend_version(),
            supported_languages=self.supported_languages(),
            supported_node_types=[
                t.value for t in self.describe_capabilities().supported_node_types
            ],
            limitations=["heuristic JS/TS parser fallback"],
        )

    async def index_files(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendResult:
        result = BackendResult(_BACKEND_ID, self.backend_version())
        ts_files = [path for path in files if path.suffix in _EXTENSIONS]
        module_nodes: dict[str, str] = {}
        symbols: dict[str, str] = {}
        for path in ts_files:
            rel = str(path.relative_to(context.repo_root)).replace("\\", "/")
            text = path.read_text(errors="replace")
            module_id = make_node_id(context.repo_ref.repo_id, "module", rel)
            module_nodes[rel] = module_id
            result.nodes.append(
                _node(
                    context, module_id, GraphNodeType.module, Path(rel).stem, rel, rel
                )
            )
            symbols.update(_symbols(context, rel, text, module_id, result))
            result.files_processed += 1

        for path in ts_files:
            rel = str(path.relative_to(context.repo_root)).replace("\\", "/")
            text = path.read_text(errors="replace")
            source_id = module_nodes[rel]
            for target in _IMPORT_RE.findall(text):
                target_rel = _resolve_import(rel, target, module_nodes)
                if target_rel and target_rel in module_nodes:
                    result.edges.append(
                        _edge(
                            context,
                            GraphEdgeType.imports,
                            source_id,
                            module_nodes[target_rel],
                            rel,
                        )
                    )
            for call_match in _CALL_RE.finditer(text):
                caller = _enclosing_function(text, symbols, rel, call_match.start())
                callee = symbols.get(f"{rel}::{call_match.group(1)}")
                if caller and callee and callee != caller:
                    result.edges.append(
                        _edge(context, GraphEdgeType.calls, caller, callee, rel)
                    )

        _add_package_evidence(context, result)
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
            _BACKEND_ID,
            file=file_path,
            span=span,
        ),
        properties={"language": "typescript"},
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
            _BACKEND_ID,
            file=file_path,
            confidence=0.7,
        ),
        confidence=0.7,
        properties={"agreement": "candidate"},
        created_ts=_now(),
    )


def _symbols(
    context: IndexingContext,
    rel: str,
    text: str,
    module_id: str,
    result: BackendResult,
) -> dict[str, str]:
    found: dict[str, str] = {}
    for regex, node_type in [
        (_CLASS_RE, GraphNodeType.class_),
        (_INTERFACE_RE, GraphNodeType.interface),
        (_FUNC_RE, GraphNodeType.function),
    ]:
        for match in regex.finditer(text):
            name = match.group(1)
            line = text[: match.start()].count("\n") + 1
            span = SourceSpan(file_path=rel, start_line=line, end_line=line)
            node_id = make_node_id(
                context.repo_ref.repo_id, node_type.value, f"{rel}::{name}"
            )
            found[f"{rel}::{name}"] = node_id
            result.nodes.append(
                _node(context, node_id, node_type, name, name, rel, span)
            )
            result.edges.append(
                _edge(context, GraphEdgeType.contains, module_id, node_id, rel)
            )
    return found


def _resolve_import(
    source_rel: str, specifier: str, modules: dict[str, str]
) -> str | None:
    if not specifier.startswith("."):
        return None
    base = Path(source_rel).parent / specifier
    for suffix in [".ts", ".tsx", ".js", ".jsx"]:
        candidate = str(base.with_suffix(suffix)).replace("\\", "/")
        if candidate in modules:
            return candidate
    return None


def _enclosing_function(
    text: str, symbols: dict[str, str], rel: str, offset: int
) -> str | None:
    current: str | None = None
    for match in _FUNC_RE.finditer(text):
        if match.start() > offset:
            break
        node_id = symbols.get(f"{rel}::{match.group(1)}")
        if node_id:
            current = node_id
    return current


def _add_package_evidence(context: IndexingContext, result: BackendResult) -> None:
    package = read_package_metadata(context.repo_root)
    result.diagnostics.extend(package.diagnostics)
    runners = detect_test_runners(context.repo_root, package)
    for script, command in package.scripts.items():
        node_id = make_node_id(
            context.repo_ref.repo_id, "build_target", f"package:{script}"
        )
        result.nodes.append(
            GraphNode(
                node_id=node_id,
                node_type=GraphNodeType.build_target,
                label=script,
                qualified_name=f"package.json::{script}",
                repo=context.repo_ref,
                snapshot=context.snapshot_ref,
                file_path="package.json",
                provenance=make_provenance(
                    context.repo_ref,
                    context.snapshot_ref,
                    source_tool=f"llm-sca-tooling.indexer.{_BACKEND_ID}.package",
                    derivation=DerivationType.heuristic,
                    evidence_strength=EvidenceStrength.structured_repository,
                    confidence=0.7,
                    file="package.json",
                ),
                properties={"command": command},
                created_ts=_now(),
            )
        )
    for runner in runners:
        node_id = make_node_id(context.repo_ref.repo_id, "ci_job", f"js-test:{runner}")
        result.nodes.append(
            GraphNode(
                node_id=node_id,
                node_type=GraphNodeType.ci_job,
                label=runner,
                qualified_name=f"test-runner::{runner}",
                repo=context.repo_ref,
                snapshot=context.snapshot_ref,
                file_path="package.json",
                provenance=make_provenance(
                    context.repo_ref,
                    context.snapshot_ref,
                    source_tool=f"llm-sca-tooling.indexer.{_BACKEND_ID}.tests",
                    derivation=DerivationType.heuristic,
                    evidence_strength=EvidenceStrength.structured_repository,
                    confidence=0.7,
                    file="package.json",
                ),
                properties={"runner": runner},
                created_ts=_now(),
            )
        )
