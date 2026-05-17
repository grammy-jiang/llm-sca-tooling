"""Markdown indexer backend — emits heading nodes with file:line spans.

Closes May-2026 audit Finding 4: prior to this backend the indexer detected
``.md`` files but produced no nodes inside them, so ``get_relevant_files``
returned Markdown evidence with ``span=null``.  Audit clauses cited against
documentation could not be pinned to exact lines.

Design:

* For each repository-relative ``.md`` file, emit one ``document`` node per
  ATX or Setext heading containing the heading text, level, and a
  :class:`SourceSpan` with ``start_line`` and ``end_line``.
* The node ``label`` is the heading text (truncated for safety) and the
  ``qualified_name`` encodes the breadcrumb path (e.g. ``README#Setup``).
* Skip headings inside fenced code blocks — ``markdown-it-py`` handles
  this distinction natively, so we do not need a hand-rolled tokenizer.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import (
    BackendCapabilities,
    BackendResult,
    IndexingContext,
)
from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity, IndexingDiagnostic
from llm_sca_tooling.indexing.hashing import make_node_id
from llm_sca_tooling.indexing.provenance import parser_provenance
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode, GraphNodeType
from llm_sca_tooling.schemas.provenance import SourceSpan
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["MarkdownBackend"]

_BACKEND_ID = "markdown"
_MAX_HEADING_LABEL = 200


def _heading_text(tokens: Sequence[object], inline_idx: int) -> str:
    """Concatenate the inline children of an inline token into plain text."""
    inline = tokens[inline_idx]
    children = getattr(inline, "children", None) or []
    parts: list[str] = []
    for child in children:
        ttype = getattr(child, "type", "")
        if ttype == "text" or ttype == "code_inline":
            parts.append(getattr(child, "content", ""))
        elif ttype == "softbreak" or ttype == "hardbreak":
            parts.append(" ")
    return " ".join(part.strip() for part in parts if part.strip())


logger = get_logger(__name__)


class MarkdownBackend:
    """Indexes Markdown documents into heading-scoped graph nodes."""

    @property
    def backend_id(self) -> str:
        return _BACKEND_ID

    def backend_version(self) -> str | None:
        try:
            from importlib.metadata import version

            return version("markdown-it-py")
        except Exception:  # noqa: BLE001
            return None

    def supported_languages(self) -> list[str]:
        return ["markdown"]

    async def detect_capabilities(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendCapabilities:
        try:
            import markdown_it  # noqa: F401

            installed = True
        except Exception:  # noqa: BLE001
            installed = False
        return BackendCapabilities(
            backend_id=_BACKEND_ID,
            installed=installed,
            version=self.backend_version(),
            supported_languages=self.supported_languages(),
            supported_node_types=["document"],
            requires_binary=False,
            limitations=(
                []
                if installed
                else ["markdown-it-py not installed; markdown spans unavailable"]
            ),
        )

    async def index_files(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendResult:
        result = BackendResult(
            backend_id=_BACKEND_ID, backend_version=self.backend_version()
        )
        md_files = [
            path for path in files if path.suffix.lower() in {".md", ".markdown"}
        ]
        if not md_files:
            result.finish()
            return result
        loop = asyncio.get_running_loop()
        for path in md_files:
            try:
                nodes, edges, diags = await loop.run_in_executor(
                    None, self._index_file, path, context
                )
                result.nodes.extend(nodes)
                result.edges.extend(edges)
                result.diagnostics.extend(diags)
                result.files_processed += 1
            except Exception as exc:  # noqa: BLE001
                result.diagnostics.append(
                    IndexingDiagnostic(
                        severity=DiagnosticSeverity.warning,
                        code="MARKDOWN_INDEX_ERROR",
                        message=f"Failed to index {path.name}: {exc}",
                        file_path=str(path.relative_to(context.repo_root)),
                        backend_id=_BACKEND_ID,
                    )
                )
                result.files_skipped += 1
        result.finish()
        return result

    def _index_file(
        self,
        path: Path,
        context: IndexingContext,
    ) -> tuple[list[GraphNode], list[GraphEdge], list[IndexingDiagnostic]]:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        diags: list[IndexingDiagnostic] = []

        rel_path = str(path.relative_to(context.repo_root)).replace("\\", "/")
        repo_ref = context.repo_ref
        snap_ref = context.snapshot_ref
        now = snap_ref.captured_ts
        prov = parser_provenance(repo_ref, snap_ref, backend_id=_BACKEND_ID)

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            diags.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.warning,
                    code="MARKDOWN_READ_ERROR",
                    message=f"Could not read {rel_path}: {exc}",
                    file_path=rel_path,
                    backend_id=_BACKEND_ID,
                )
            )
            return nodes, edges, diags

        try:
            from markdown_it import MarkdownIt
        except Exception as exc:  # noqa: BLE001
            diags.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.info,
                    code="MARKDOWN_PARSER_MISSING",
                    message=f"markdown-it-py unavailable: {exc}",
                    file_path=rel_path,
                    backend_id=_BACKEND_ID,
                )
            )
            return nodes, edges, diags

        md = MarkdownIt("commonmark")
        tokens = md.parse(source)
        breadcrumb: list[tuple[int, str]] = []
        for idx, tok in enumerate(tokens):
            if getattr(tok, "type", "") != "heading_open":
                continue
            level = int(getattr(tok, "tag", "h1")[1:])
            inline_idx = idx + 1
            text = _heading_text(tokens, inline_idx) or "(untitled)"
            label = text[:_MAX_HEADING_LABEL]
            line_map = getattr(tok, "map", None)
            if not line_map:
                continue
            start_line = line_map[0] + 1
            end_line = max(start_line, line_map[1])
            while breadcrumb and breadcrumb[-1][0] >= level:
                breadcrumb.pop()
            breadcrumb.append((level, label))
            qual_name = rel_path + "#" + " > ".join(crumb for _, crumb in breadcrumb)
            span = SourceSpan(
                file_path=rel_path,
                start_line=start_line,
                end_line=end_line,
            )
            node_id = make_node_id(
                repo_ref.repo_id, "document", f"{rel_path}#L{start_line}"
            )
            nodes.append(
                GraphNode(
                    node_id=node_id,
                    node_type=GraphNodeType.document,
                    label=label,
                    qualified_name=qual_name,
                    file_path=rel_path,
                    repo=repo_ref,
                    snapshot=snap_ref,
                    span=span,
                    provenance=prov,
                    properties={
                        "kind": "heading",
                        "level": level,
                        "text": text,
                        "breadcrumb": [crumb for _, crumb in breadcrumb],
                    },
                    created_ts=now,
                )
            )
        return nodes, edges, diags
