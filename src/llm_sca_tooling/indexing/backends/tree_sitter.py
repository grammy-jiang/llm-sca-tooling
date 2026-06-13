"""Tree-sitter backend — multi-language real-grammar structural tier.

Tree-sitter parses with the language's real grammar (not regex), but resolves
no semantics (no cross-file calls). It therefore sits between the heuristic
regex backends and the dedicated semantic backends (ts-morph, libclang) in
confidence: where a dedicated backend is present the reconciler prefers it and
marks the tree-sitter facts as confirming agreement; where no toolchain is
installed, tree-sitter still gives real-grammar symbols (better than regex).

Each grammar is an optional dependency loaded per-language; a missing grammar
degrades that language gracefully without affecting the others.
"""

from __future__ import annotations

import asyncio
import importlib
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from llm_sca_tooling.indexing.backends.base import (
    BackendCapabilities,
    BackendResult,
    IndexingContext,
)
from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity, IndexingDiagnostic
from llm_sca_tooling.indexing.hashing import make_node_id
from llm_sca_tooling.indexing.provenance import parser_provenance
from llm_sca_tooling.schemas.graph import GraphNode, GraphNodeType
from llm_sca_tooling.schemas.provenance import SourceSpan
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["TreeSitterBackend"]

if TYPE_CHECKING:
    from tree_sitter import Language

logger = get_logger(__name__)

_BACKEND_ID = "tree_sitter"
# Real grammar parse, no semantics: above regex heuristic (0.6), below the
# dedicated semantic backends (ts-morph / libclang at 1.0).
_CONFIDENCE = 0.8

_CLASS = GraphNodeType.class_
_FUNC = GraphNodeType.function
_IFACE = GraphNodeType.interface


@dataclass(frozen=True)
class _Grammar:
    module: str
    factory: str
    sep: str  # qualified-name separator for nested methods
    # tree-sitter node type -> graph node type
    node_types: dict[str, GraphNodeType]


_GRAMMARS: dict[str, _Grammar] = {
    "python": _Grammar(
        "tree_sitter_python",
        "language",
        ".",
        {"class_definition": _CLASS, "function_definition": _FUNC},
    ),
    "typescript": _Grammar(
        "tree_sitter_typescript",
        "language_typescript",
        ".",
        {
            "class_declaration": _CLASS,
            "function_declaration": _FUNC,
            "method_definition": _FUNC,
            "interface_declaration": _IFACE,
            "enum_declaration": _CLASS,
        },
    ),
    "tsx": _Grammar(
        "tree_sitter_typescript",
        "language_tsx",
        ".",
        {
            "class_declaration": _CLASS,
            "function_declaration": _FUNC,
            "method_definition": _FUNC,
            "interface_declaration": _IFACE,
            "enum_declaration": _CLASS,
        },
    ),
    "javascript": _Grammar(
        "tree_sitter_javascript",
        "language",
        ".",
        {
            "class_declaration": _CLASS,
            "function_declaration": _FUNC,
            "method_definition": _FUNC,
        },
    ),
    "c": _Grammar(
        "tree_sitter_c",
        "language",
        "::",
        {"struct_specifier": _CLASS, "function_definition": _FUNC},
    ),
    "cpp": _Grammar(
        "tree_sitter_cpp",
        "language",
        "::",
        {
            "class_specifier": _CLASS,
            "struct_specifier": _CLASS,
            "function_definition": _FUNC,
        },
    ),
}

_EXT_TO_LANG = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".c": "c",
    ".h": "cpp",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".hxx": "cpp",
}

# Class-like container node types whose name qualifies nested methods.
_CONTAINER_TYPES = {
    "class_definition",
    "class_declaration",
    "class_specifier",
    "struct_specifier",
}
# Declarator identifier node types (C/C++ function names live in declarators).
_NAME_NODE_TYPES = {
    "identifier",
    "field_identifier",
    "qualified_identifier",
    "type_identifier",
}


@cache
def _load_language(lang_key: str) -> Language | None:
    spec = _GRAMMARS.get(lang_key)
    if spec is None:
        return None
    try:
        from tree_sitter import Language  # noqa: PLC0415

        module = importlib.import_module(spec.module)
        return Language(getattr(module, spec.factory)())
    except Exception:  # noqa: BLE001 - missing grammar -> language unavailable
        return None


def _available_languages() -> list[str]:
    return [k for k in _GRAMMARS if _load_language(k) is not None]


class TreeSitterBackend:
    """Multi-language tree-sitter structural backend (optional grammars)."""

    @property
    def backend_id(self) -> str:
        return _BACKEND_ID

    def backend_version(self) -> str | None:
        return "tree-sitter" if _available_languages() else None

    def supported_languages(self) -> list[str]:
        return sorted(set(_available_languages()))

    async def detect_capabilities(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendCapabilities:
        langs = self.supported_languages()
        return BackendCapabilities(
            backend_id=_BACKEND_ID,
            installed=bool(langs),
            version=self.backend_version(),
            supported_languages=langs,
            supported_node_types=["module", "class", "function", "interface"],
            requires_binary=False,
            limitations=([] if langs else ["no tree-sitter grammars installed"]),
        )

    async def index_files(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendResult:
        result = BackendResult(
            backend_id=_BACKEND_ID, backend_version=self.backend_version()
        )
        if not self.supported_languages():
            result.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.info,
                    code="TREE_SITTER_UNAVAILABLE",
                    message="no tree-sitter grammars installed; enrichment skipped",
                    backend_id=_BACKEND_ID,
                )
            )
            result.finish()
            return result

        loop = asyncio.get_running_loop()
        for path in files:
            lang_key = _EXT_TO_LANG.get(path.suffix)
            if lang_key is None or _load_language(lang_key) is None:
                continue
            try:
                nodes, diags = await loop.run_in_executor(
                    None, self._parse_file, path, lang_key, context
                )
                result.nodes.extend(nodes)
                result.diagnostics.extend(diags)
                result.files_processed += 1
            except Exception as exc:  # noqa: BLE001
                result.diagnostics.append(
                    IndexingDiagnostic(
                        severity=DiagnosticSeverity.warning,
                        code="TREE_SITTER_PARSE_ERROR",
                        message=f"tree-sitter failed for {path.name}: {exc}",
                        file_path=str(path.relative_to(context.repo_root)),
                        backend_id=_BACKEND_ID,
                    )
                )
                result.files_skipped += 1

        result.finish()
        return result

    def _parse_file(
        self, path: Path, lang_key: str, context: IndexingContext
    ) -> tuple[list[GraphNode], list[IndexingDiagnostic]]:
        from tree_sitter import Parser  # noqa: PLC0415

        spec = _GRAMMARS[lang_key]
        language = _load_language(lang_key)
        assert language is not None
        nodes: list[GraphNode] = []
        diags: list[IndexingDiagnostic] = []
        rel = str(path.relative_to(context.repo_root)).replace("\\", "/")

        source = path.read_bytes()
        tree = Parser(language).parse(source)
        if tree.root_node.has_error:
            diags.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.info,
                    code="TREE_SITTER_SYNTAX_ERROR",
                    message=f"tree-sitter parse error in {rel}",
                    file_path=rel,
                    backend_id=_BACKEND_ID,
                )
            )

        seen: set[str] = set()
        self._walk(tree.root_node, source, spec, rel, context, None, seen, nodes)
        return nodes, diags

    def _walk(
        self,
        node: Any,
        source: bytes,
        spec: _Grammar,
        rel: str,
        context: IndexingContext,
        enclosing: str | None,
        seen: set[str],
        out: list[GraphNode],
    ) -> None:
        next_enclosing = enclosing
        graph_type = spec.node_types.get(node.type)
        if graph_type is not None:
            name = _symbol_name(node, source)
            if name:
                qualified = name
                # Qualify a method/inline function with its enclosing class
                # unless the name is already qualified (e.g. C++ Calc::compute).
                if enclosing and graph_type is _FUNC and spec.sep not in name:
                    qualified = f"{enclosing}{spec.sep}{name}"
                emitted = self._emit(
                    node, graph_type, name, qualified, rel, context, seen, out
                )
                if emitted and node.type in _CONTAINER_TYPES:
                    next_enclosing = name
        if node.type in _CONTAINER_TYPES and next_enclosing is None:
            cname = _symbol_name(node, source)
            if cname:
                next_enclosing = cname

        for child in node.children:
            self._walk(child, source, spec, rel, context, next_enclosing, seen, out)

    def _emit(
        self,
        node: Any,
        graph_type: GraphNodeType,
        label: str,
        qualified: str,
        rel: str,
        context: IndexingContext,
        seen: set[str],
        out: list[GraphNode],
    ) -> bool:
        node_id = make_node_id(
            context.repo_ref.repo_id, graph_type.value, f"{rel}::ts::{qualified}"
        )
        if node_id in seen:
            return False
        seen.add(node_id)
        span = SourceSpan(
            file_path=rel,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            byte_start=node.start_byte,
            byte_end=node.end_byte,
        )
        out.append(
            GraphNode(
                node_id=node_id,
                node_type=graph_type,
                label=label,
                qualified_name=qualified,
                file_path=rel,
                span=span,
                repo=context.repo_ref,
                snapshot=context.snapshot_ref,
                provenance=parser_provenance(
                    context.repo_ref,
                    context.snapshot_ref,
                    _BACKEND_ID,
                    file=rel,
                    span=span,
                    confidence=_CONFIDENCE,
                ),
                properties={"source": "tree_sitter"},
                created_ts=context.snapshot_ref.captured_ts,
            )
        )
        return True


def _symbol_name(node: Any, source: bytes) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return source[name_node.start_byte : name_node.end_byte].decode(
            errors="replace"
        )
    declarator = node.child_by_field_name("declarator")
    if declarator is not None:
        ident = _find_declarator_name(declarator)
        if ident is not None:
            return source[ident.start_byte : ident.end_byte].decode(errors="replace")
    return None


def _find_declarator_name(node: Any) -> Any | None:
    """Descend a C/C++ declarator to the innermost identifier."""
    if node.type in _NAME_NODE_TYPES:
        return node
    inner = node.child_by_field_name("declarator")
    if inner is not None:
        return _find_declarator_name(inner)
    for child in node.children:
        found = _find_declarator_name(child)
        if found is not None:
            return found
    return None
