"""Tree-sitter backend — optional syntax enricher.

Degrades gracefully when the grammar package is unavailable.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

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


def _try_import_tree_sitter() -> tuple[Language | None, str | None]:
    """Return (language, version_str) or (None, None) if unavailable."""
    try:
        import tree_sitter_python as tsp
        from tree_sitter import Language

        py_lang = Language(tsp.language())
        return py_lang, "0.25"
    except Exception:
        return None, None


class TreeSitterBackend:
    """Optional tree-sitter backend that enriches syntax spans."""

    @property
    def backend_id(self) -> str:
        return _BACKEND_ID

    def backend_version(self) -> str | None:
        _, v = _try_import_tree_sitter()
        return v

    def supported_languages(self) -> list[str]:
        return ["python"]

    async def detect_capabilities(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendCapabilities:
        lang, version = _try_import_tree_sitter()
        return BackendCapabilities(
            backend_id=_BACKEND_ID,
            installed=lang is not None,
            version=version,
            supported_languages=["python"],
            supported_node_types=["module", "class", "function", "method"],
            requires_binary=False,
            limitations=["Python grammar only in Phase 3"],
        )

    async def index_files(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendResult:
        result = BackendResult(
            backend_id=_BACKEND_ID, backend_version=self.backend_version()
        )
        lang, version = _try_import_tree_sitter()

        if lang is None:
            result.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.info,
                    code="TREE_SITTER_UNAVAILABLE",
                    message="tree-sitter-python grammar not available; skipping tree-sitter enrichment",
                    backend_id=_BACKEND_ID,
                )
            )
            result.finish()
            return result

        py_files = [f for f in files if f.suffix == ".py"]
        loop = asyncio.get_running_loop()

        for path in py_files:
            try:
                nodes, diags = await loop.run_in_executor(
                    None, self._parse_file, path, lang, context
                )
                result.nodes.extend(nodes)
                result.diagnostics.extend(diags)
                result.files_processed += 1
            except Exception as exc:
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
        self,
        path: Path,
        language: Language,
        context: IndexingContext,
    ) -> tuple[list[GraphNode], list[IndexingDiagnostic]]:
        from tree_sitter import Parser

        nodes: list[GraphNode] = []
        diags: list[IndexingDiagnostic] = []
        rel_path = str(path.relative_to(context.repo_root)).replace("\\", "/")

        source = path.read_bytes()
        parser = Parser(language)
        tree = parser.parse(source)

        if tree.root_node.has_error:
            diags.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.warning,
                    code="TREE_SITTER_SYNTAX_ERROR",
                    message=f"tree-sitter parse error in {rel_path}",
                    file_path=rel_path,
                    backend_id=_BACKEND_ID,
                )
            )

        now = context.snapshot_ref.captured_ts
        for child in tree.root_node.children:
            if child.type in ("class_definition", "function_definition"):
                name_node = child.child_by_field_name("name")
                if name_node is None:
                    continue
                name = source[name_node.start_byte : name_node.end_byte].decode(
                    errors="replace"
                )
                node_type = (
                    GraphNodeType.class_
                    if child.type == "class_definition"
                    else GraphNodeType.function
                )
                span = SourceSpan(
                    file_path=rel_path,
                    start_line=child.start_point[0] + 1,
                    end_line=child.end_point[0] + 1,
                    byte_start=child.start_byte,
                    byte_end=child.end_byte,
                )
                prov = parser_provenance(
                    context.repo_ref,
                    context.snapshot_ref,
                    _BACKEND_ID,
                    file=rel_path,
                    span=span,
                )
                node_id = make_node_id(
                    context.repo_ref.repo_id,
                    node_type.value,
                    f"{rel_path}::ts::{name}",
                )
                nodes.append(
                    GraphNode(
                        node_id=node_id,
                        node_type=node_type,
                        label=name,
                        qualified_name=name,
                        file_path=rel_path,
                        span=span,
                        repo=context.repo_ref,
                        snapshot=context.snapshot_ref,
                        provenance=prov,
                        properties={"source": "tree_sitter"},
                        created_ts=now,
                    )
                )

        return nodes, diags
