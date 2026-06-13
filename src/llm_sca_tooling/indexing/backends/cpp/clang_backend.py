"""Real C/C++ backend driven by libclang (``clang.cindex``).

Parses translation units with clang and emits parser-grade graph facts:
struct/class/function/method symbols, ``#include`` edges, and cross-file call
edges resolved through clang's AST (``cursor.referenced``) — facts the regex
fallback cannot produce. Runs in-process via the ``libclang`` wheel (no system
toolchain). When libclang is unavailable or a parse fails, delegates to the
heuristic regex backend so indexing always degrades gracefully.

Compile flags come from ``compile_commands.json`` at the repo root when
present; otherwise a self-contained default is used, which still resolves
intra-TU symbols and anything reached through ``#include``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llm_sca_tooling.indexing.backends.base import (
    BackendCapabilities,
    BackendResult,
    IndexingContext,
)
from llm_sca_tooling.indexing.backends.cpp.cpp_backend import CppBackend
from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity, IndexingDiagnostic
from llm_sca_tooling.indexing.hashing import make_edge_id, make_node_id
from llm_sca_tooling.indexing.provenance import parser_provenance
from llm_sca_tooling.schemas.graph import (
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
)
from llm_sca_tooling.schemas.provenance import SourceSpan

__all__ = ["ClangCppBackend"]

_BACKEND_ID = "cpp.libclang"
_TU_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".cu"}
_HEADER_EXTENSIONS = {".h", ".hpp", ".hh", ".hxx"}
_ALL_EXTENSIONS = _TU_EXTENSIONS | _HEADER_EXTENSIONS
_DEFAULT_ARGS = ["-std=c++17"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ClangCppBackend:
    """libclang-backed C/C++ backend with regex-fallback delegation."""

    def __init__(self) -> None:
        self._fallback = CppBackend()
        self._resolved_version: str | None = None

    @property
    def backend_id(self) -> str:
        return _BACKEND_ID

    def backend_version(self) -> str | None:
        return self._resolved_version or "libclang"

    def supported_languages(self) -> list[str]:
        return ["c", "cpp"]

    def is_available(self) -> bool:
        """libclang wheel importable and a native lib that loads."""
        try:
            import clang.cindex as cindex  # noqa: PLC0415

            cindex.Index.create()
        except Exception:  # noqa: BLE001 - any import/load failure -> unavailable
            return False
        return True

    async def detect_capabilities(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendCapabilities:
        available = self.is_available()
        return BackendCapabilities(
            backend_id=_BACKEND_ID,
            installed=available,
            version=self.backend_version() if available else None,
            supported_languages=self.supported_languages(),
            supported_node_types=[
                GraphNodeType.module.value,
                GraphNodeType.class_.value,
                GraphNodeType.function.value,
            ],
            requires_binary=True,
            limitations=(
                []
                if available
                else ["libclang unavailable; delegating to regex fallback"]
            ),
        )

    async def index_files(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendResult:
        cpp_files = [p for p in files if p.suffix in _ALL_EXTENSIONS]
        if not self.is_available() or not cpp_files:
            return await self._fallback.index_files(context, files)
        try:
            return self._index_with_clang(context, cpp_files)
        except Exception as exc:  # noqa: BLE001
            result = await self._fallback.index_files(context, files)
            result.diagnostics.append(
                IndexingDiagnostic(
                    code="clang_backend_failed",
                    message=f"libclang backend failed ({exc}); used regex fallback",
                    severity=DiagnosticSeverity.warning,
                    backend_id=_BACKEND_ID,
                )
            )
            return result

    # ── clang indexing ───────────────────────────────────────────────────────

    def _index_with_clang(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendResult:
        import clang.cindex as cindex  # noqa: PLC0415

        self._resolved_version = "libclang"
        result = BackendResult(_BACKEND_ID, self.backend_version())
        repo_root = context.repo_root
        repo_id = context.repo_ref.repo_id
        indexed = {self._rel(repo_root, p) for p in files}
        compile_args = _load_compile_commands(repo_root)

        index = cindex.Index.create()
        module_ids: dict[str, str] = {}
        seen_nodes: set[str] = set()

        # Parse translation units (and standalone headers) — symbols in any
        # indexed file reached through includes are emitted once (deduped).
        tus = [p for p in files if p.suffix in _TU_EXTENSIONS] or files
        for path in tus:
            rel = self._rel(repo_root, path)
            args = compile_args.get(rel, list(_DEFAULT_ARGS))
            if path.suffix in _HEADER_EXTENSIONS:
                args = [*args, "-x", "c++"]
            try:
                tu = index.parse(
                    str(path),
                    args=args,
                    # Required for INCLUSION_DIRECTIVE cursors (#include edges).
                    options=cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD,
                )
            except cindex.TranslationUnitLoadError as exc:
                result.diagnostics.append(
                    IndexingDiagnostic(
                        code="clang_parse_failed",
                        message=f"{rel}: {exc}",
                        severity=DiagnosticSeverity.warning,
                        backend_id=_BACKEND_ID,
                    )
                )
                continue
            self._walk(
                context,
                tu.cursor,
                indexed,
                repo_root,
                repo_id,
                module_ids,
                seen_nodes,
                result,
                current=None,
            )
            result.files_processed += 1

        result.finish()
        return result

    def _ensure_module(
        self,
        context: IndexingContext,
        rel: str,
        repo_id: str,
        module_ids: dict[str, str],
        seen: set[str],
        result: BackendResult,
    ) -> str:
        if rel in module_ids:
            return module_ids[rel]
        module_id = make_node_id(repo_id, GraphNodeType.module.value, rel)
        module_ids[rel] = module_id
        if module_id not in seen:
            seen.add(module_id)
            result.nodes.append(
                self._make_node(
                    context,
                    module_id,
                    GraphNodeType.module,
                    Path(rel).stem,
                    rel,
                    rel,
                    None,
                )
            )
        return module_id

    def _walk(
        self,
        context: IndexingContext,
        cursor: Any,
        indexed: set[str],
        repo_root: Path,
        repo_id: str,
        module_ids: dict[str, str],
        seen: set[str],
        result: BackendResult,
        current: str | None,
    ) -> None:
        import clang.cindex as cindex  # noqa: PLC0415

        loc_file = cursor.location.file
        in_repo = loc_file is not None and self._rel(
            repo_root, Path(loc_file.name)
        ) in (indexed)
        next_current = current

        if in_repo:
            rel = self._rel(repo_root, Path(loc_file.name))
            kind = cursor.kind
            if (
                kind
                in (
                    cindex.CursorKind.CLASS_DECL,
                    cindex.CursorKind.STRUCT_DECL,
                )
                and cursor.is_definition()
            ):
                self._emit_symbol(
                    context,
                    GraphNodeType.class_,
                    cursor.spelling,
                    cursor.spelling,
                    rel,
                    cursor,
                    repo_id,
                    module_ids,
                    seen,
                    result,
                )
            elif kind == cindex.CursorKind.FUNCTION_DECL and cursor.is_definition():
                name = cursor.spelling
                self._emit_symbol(
                    context,
                    GraphNodeType.function,
                    name,
                    name,
                    rel,
                    cursor,
                    repo_id,
                    module_ids,
                    seen,
                    result,
                )
                next_current = self._node_id(repo_id, GraphNodeType.function, rel, name)
            elif kind == cindex.CursorKind.CXX_METHOD and cursor.is_definition():
                parent = cursor.semantic_parent
                cls = parent.spelling if parent else ""
                qname = f"{cls}::{cursor.spelling}" if cls else cursor.spelling
                self._emit_symbol(
                    context,
                    GraphNodeType.function,
                    cursor.spelling,
                    qname,
                    rel,
                    cursor,
                    repo_id,
                    module_ids,
                    seen,
                    result,
                )
                next_current = self._node_id(
                    repo_id, GraphNodeType.function, rel, qname
                )
            elif kind == cindex.CursorKind.INCLUSION_DIRECTIVE:
                included = cursor.get_included_file()
                if included is not None:
                    inc_rel = self._rel(repo_root, Path(included.name))
                    if inc_rel in indexed:
                        src = self._ensure_module(
                            context, rel, repo_id, module_ids, seen, result
                        )
                        tgt = self._ensure_module(
                            context, inc_rel, repo_id, module_ids, seen, result
                        )
                        result.edges.append(
                            self._make_edge(
                                context, GraphEdgeType.imports, src, tgt, rel
                            )
                        )
            elif kind == cindex.CursorKind.CALL_EXPR and current is not None:
                ref = cursor.referenced
                if ref is not None and ref.location.file is not None:
                    tgt_rel = self._rel(repo_root, Path(ref.location.file.name))
                    if tgt_rel in indexed:
                        tgt_id = self._callee_node_id(repo_id, tgt_rel, ref)
                        if tgt_id and tgt_id != current:
                            result.edges.append(
                                self._make_edge(
                                    context, GraphEdgeType.calls, current, tgt_id, rel
                                )
                            )

        for child in cursor.get_children():
            self._walk(
                context,
                child,
                indexed,
                repo_root,
                repo_id,
                module_ids,
                seen,
                result,
                next_current,
            )

    def _emit_symbol(
        self,
        context: IndexingContext,
        node_type: GraphNodeType,
        label: str,
        qualified_name: str,
        rel: str,
        cursor: Any,
        repo_id: str,
        module_ids: dict[str, str],
        seen: set[str],
        result: BackendResult,
    ) -> None:
        node_id = self._node_id(repo_id, node_type, rel, qualified_name)
        if node_id in seen:
            return
        seen.add(node_id)
        extent = cursor.extent
        span = SourceSpan(
            file_path=rel,
            start_line=extent.start.line,
            end_line=extent.end.line,
        )
        result.nodes.append(
            self._make_node(
                context, node_id, node_type, label, qualified_name, rel, span
            )
        )
        module_id = self._ensure_module(context, rel, repo_id, module_ids, seen, result)
        result.edges.append(
            self._make_edge(context, GraphEdgeType.contains, module_id, node_id, rel)
        )

    @staticmethod
    def _rel(repo_root: Path, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(repo_root.resolve())).replace(
                "\\", "/"
            )
        except ValueError:
            return str(path).replace("\\", "/")

    @staticmethod
    def _node_id(
        repo_id: str, node_type: GraphNodeType, rel: str, qualified_name: str
    ) -> str:
        return make_node_id(repo_id, node_type.value, f"{rel}::{qualified_name}")

    def _callee_node_id(self, repo_id: str, rel: str, ref: Any) -> str | None:
        import clang.cindex as cindex  # noqa: PLC0415

        if ref.kind == cindex.CursorKind.CXX_METHOD:
            parent = ref.semantic_parent
            cls = parent.spelling if parent else ""
            qname = f"{cls}::{ref.spelling}" if cls else ref.spelling
        elif ref.kind == cindex.CursorKind.FUNCTION_DECL:
            qname = ref.spelling
        else:
            return None
        return self._node_id(repo_id, GraphNodeType.function, rel, qname)

    def _make_node(
        self,
        context: IndexingContext,
        node_id: str,
        node_type: GraphNodeType,
        label: str,
        qualified_name: str,
        file_path: str,
        span: SourceSpan | None,
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
            properties={"language": "cpp", "parser": "libclang"},
            created_ts=_now(),
        )

    def _make_edge(
        self,
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
                confidence=0.95,
            ),
            confidence=0.95,
            properties={"agreement": "confirmed", "parser": "libclang"},
            created_ts=_now(),
        )


def _load_compile_commands(repo_root: Path) -> dict[str, list[str]]:
    """Map repo-relative file -> compile args from compile_commands.json."""
    cc_path = repo_root / "compile_commands.json"
    if not cc_path.is_file():
        return {}
    try:
        entries = json.loads(cc_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, list[str]] = {}
    for entry in entries:
        try:
            file_path = Path(entry["file"])
            rel = str(file_path.resolve().relative_to(repo_root.resolve())).replace(
                "\\", "/"
            )
        except (KeyError, ValueError):
            continue
        args = entry.get("arguments")
        if isinstance(args, list) and len(args) > 1:
            # Drop the compiler argv[0] and the input file itself.
            out[rel] = [a for a in args[1:] if a != entry.get("file")]
    return out
