"""Python AST backend — deterministic symbol/import indexing using stdlib ast.

This backend is the core of Phase 3. It is always available (no external
binary required) and produces hard_static evidence for modules, classes,
functions, methods, imports, and test nodes.
"""

from __future__ import annotations

import ast
import asyncio
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import (
    BackendCapabilities,
    BackendResult,
    IndexingContext,
)
from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity, IndexingDiagnostic
from llm_sca_tooling.indexing.hashing import make_edge_id, make_node_id
from llm_sca_tooling.indexing.provenance import parser_provenance
from llm_sca_tooling.schemas.graph import (
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
)
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef, SourceSpan
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["PythonASTBackend", "ImportResolution", "ImportClassification"]

logger = get_logger(__name__)

_BACKEND_ID = "python_ast"


class ImportResolution(str, Enum):
    resolved_internal = "resolved_internal"
    external_dependency = "external_dependency"
    unresolved = "unresolved"
    ambiguous = "ambiguous"


@dataclass
class ImportClassification:
    resolution: ImportResolution
    target_path: str | None = None  # repo-relative file path if resolved_internal


def _node_span(node: ast.AST, filename: str) -> SourceSpan:
    return SourceSpan(
        file_path=filename,
        start_line=getattr(node, "lineno", 1),
        end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
        start_col=getattr(node, "col_offset", None),
        end_col=getattr(node, "end_col_offset", None),
    )


def _make_qual_name(scope: list[str], name: str) -> str:
    """Build a qualified name from a scope stack and a local name."""
    if scope:
        return ".".join(scope) + "." + name
    return name


def _file_to_module(rel_path: str) -> str:
    """Convert a repo-relative path like src/pkg/module.py to src.pkg.module."""
    return rel_path.replace("/", ".").replace("\\", ".").removesuffix(".py")


def classify_import(
    module_name: str | None,
    names: list[str],
    is_relative: bool,
    level: int,
    current_module: str,
    repo_root: Path,
    rel_file: str,
) -> ImportClassification:
    """Classify an import statement as internal, external, unresolved, or ambiguous.

    Args:
        module_name: The ``import X`` or ``from X import ...`` module name (None for relative-only).
        names: The names being imported (e.g. ``["parse"]`` for ``from X import parse``).
        is_relative: Whether the import uses leading dots (relative import).
        level: Number of leading dots (0 = absolute, 1 = from ., 2 = from ..).
        current_module: Dotted module path of the importing file.
        repo_root: Repository root path.
        rel_file: Repository-relative file path of the importing file.

    Returns:
        An :class:`ImportClassification` with the resolution type and optional
        target file path for resolved internal imports.

    Decision logic:
    - Relative imports always resolve internally (or fail with unresolved).
    - Absolute imports resolve internally when the top-level package exists in the repo.
    - Standard library modules and third-party packages are external_dependency.
    - Unresolvable module names are unresolved.
    - Star imports are ambiguous when the source module is external.
    """
    if is_relative or level > 0:
        # Relative import — try to resolve within the repo
        parts = current_module.split(".")
        # Go up `level` levels
        base_parts = parts[: max(0, len(parts) - level)]
        if module_name:
            candidate_parts = base_parts + module_name.split(".")
        else:
            candidate_parts = base_parts
        candidate_path = Path(repo_root) / Path(*candidate_parts).with_suffix(".py")
        rel_candidate = (
            str(candidate_path.relative_to(repo_root))
            if candidate_path.exists()
            else None
        )
        # Also try as a package
        if rel_candidate is None:
            pkg_path = Path(repo_root) / Path(*candidate_parts) / "__init__.py"
            if pkg_path.exists():
                rel_candidate = str(
                    (Path(repo_root) / Path(*candidate_parts)).relative_to(repo_root)
                )
        if rel_candidate is not None:
            return ImportClassification(
                resolution=ImportResolution.resolved_internal,
                target_path=rel_candidate.replace("\\", "/"),
            )
        return ImportClassification(resolution=ImportResolution.unresolved)

    # Absolute import
    if not module_name:
        return ImportClassification(resolution=ImportResolution.unresolved)

    top = module_name.split(".")[0]

    internal_paths = [
        repo_root / module_name.replace(".", "/") / "__init__.py",
        (repo_root / module_name.replace(".", "/")).with_suffix(".py"),
        repo_root / "src" / module_name.replace(".", "/") / "__init__.py",
        (repo_root / "src" / module_name.replace(".", "/")).with_suffix(".py"),
    ]
    for p in internal_paths:
        if p.exists():
            rel = str(p.relative_to(repo_root)).replace("\\", "/")
            # Normalize __init__.py to its directory
            if rel.endswith("/__init__.py"):
                rel = rel[: -len("/__init__.py")]
            return ImportClassification(
                resolution=ImportResolution.resolved_internal,
                target_path=rel,
            )

    # Check stdlib
    if top in sys.stdlib_module_names:
        return ImportClassification(resolution=ImportResolution.external_dependency)

    # Unknown — treat as external (could be third-party)
    return ImportClassification(resolution=ImportResolution.external_dependency)


class PythonASTBackend:
    """Index Python files using the standard library ``ast`` module."""

    @property
    def backend_id(self) -> str:
        return _BACKEND_ID

    def backend_version(self) -> str | None:
        return f"python/{sys.version_info.major}.{sys.version_info.minor}"

    def supported_languages(self) -> list[str]:
        return ["python"]

    async def detect_capabilities(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendCapabilities:
        return BackendCapabilities(
            backend_id=_BACKEND_ID,
            installed=True,
            version=self.backend_version(),
            supported_languages=["python"],
            supported_node_types=["module", "class", "function", "method", "test"],
            requires_binary=False,
        )

    async def index_files(
        self, context: IndexingContext, files: list[Path]
    ) -> BackendResult:
        result = BackendResult(
            backend_id=_BACKEND_ID,
            backend_version=self.backend_version(),
        )
        py_files = [f for f in files if f.suffix == ".py"]

        loop = asyncio.get_running_loop()
        for path in py_files:
            try:
                nodes, edges, diags = await loop.run_in_executor(
                    None,
                    self._index_file,
                    path,
                    context,
                )
                result.nodes.extend(nodes)
                result.edges.extend(edges)
                result.diagnostics.extend(diags)
                # Count as skipped if parsing failed (syntax error in diags)
                had_syntax_error = any("SYNTAX_ERROR" in d.code for d in diags)
                if had_syntax_error:
                    result.files_skipped += 1
                else:
                    result.files_processed += 1
            except Exception as exc:
                result.diagnostics.append(
                    IndexingDiagnostic(
                        severity=DiagnosticSeverity.warning,
                        code="PYTHON_INDEX_ERROR",
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
        now_str = snap_ref.captured_ts

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            diags.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.warning,
                    code="PYTHON_SYNTAX_ERROR",
                    message=f"Syntax error in {rel_path}: {exc}",
                    file_path=rel_path,
                    backend_id=_BACKEND_ID,
                )
            )
            return nodes, edges, diags

        current_module = _file_to_module(rel_path)

        # Module node (already emitted by scanner, but enrich with AST metadata)
        module_id = make_node_id(repo_ref.repo_id, "module", rel_path)

        # Collect top-level definitions
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                self._process_definition(
                    node,
                    parent_id=module_id,
                    scope=[],
                    rel_path=rel_path,
                    repo_ref=repo_ref,
                    snap_ref=snap_ref,
                    now_str=now_str,
                    nodes=nodes,
                    edges=edges,
                )
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                self._process_import(
                    node,
                    module_id=module_id,
                    current_module=current_module,
                    rel_file=rel_path,
                    context=context,
                    repo_ref=repo_ref,
                    snap_ref=snap_ref,
                    now_str=now_str,
                    nodes=nodes,
                    edges=edges,
                    diags=diags,
                )

        self._process_calls(tree, rel_path, repo_ref, snap_ref, now_str, nodes, edges)
        return nodes, edges, diags

    def _process_definition(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        parent_id: str,
        scope: list[str],
        rel_path: str,
        repo_ref: RepoRef,
        snap_ref: SnapshotRef,
        now_str: str,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> None:
        is_method = bool(scope) and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        )
        is_test = node.name.startswith("test_") or (
            isinstance(node, ast.FunctionDef)
            and any(
                (isinstance(d, ast.Name) and "fixture" in d.id)
                or (isinstance(d, ast.Attribute) and "fixture" in d.attr)
                for d in node.decorator_list
            )
        )
        qual_name = _make_qual_name(scope, node.name)
        full_qual = f"{rel_path}::{qual_name}"

        if isinstance(node, ast.ClassDef):
            node_type = GraphNodeType.class_
        elif is_test:
            node_type = GraphNodeType.test
        elif is_method:
            node_type = GraphNodeType.method
        else:
            node_type = GraphNodeType.function

        span = _node_span(node, rel_path)
        prov = parser_provenance(
            repo_ref,
            snap_ref,
            _BACKEND_ID,
            file=rel_path,
            span=span,
        )
        node_id = make_node_id(repo_ref.repo_id, node_type.value, full_qual)
        nodes.append(
            GraphNode(
                node_id=node_id,
                node_type=node_type,
                label=node.name,
                qualified_name=qual_name,
                file_path=rel_path,
                span=span,
                repo=repo_ref,
                snapshot=snap_ref,
                provenance=prov,
                properties={
                    "is_test": is_test,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                },
                created_ts=now_str,
            )
        )
        edges.append(
            GraphEdge(
                edge_id=make_edge_id(repo_ref.repo_id, "contains", parent_id, node_id),
                edge_type=GraphEdgeType.contains,
                source_id=parent_id,
                target_id=node_id,
                repo=repo_ref,
                snapshot=snap_ref,
                provenance=prov,
                created_ts=now_str,
            )
        )

        # Recurse into class bodies for methods
        if isinstance(node, ast.ClassDef):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._process_definition(
                        child,
                        parent_id=node_id,
                        scope=scope + [node.name],
                        rel_path=rel_path,
                        repo_ref=repo_ref,
                        snap_ref=snap_ref,
                        now_str=now_str,
                        nodes=nodes,
                        edges=edges,
                    )

    def _process_import(
        self,
        node: ast.Import | ast.ImportFrom,
        module_id: str,
        current_module: str,
        rel_file: str,
        context: IndexingContext,
        repo_ref: RepoRef,
        snap_ref: SnapshotRef,
        now_str: str,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        diags: list[IndexingDiagnostic],
    ) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                classification = classify_import(
                    module_name=alias.name,
                    names=[],
                    is_relative=False,
                    level=0,
                    current_module=current_module,
                    repo_root=context.repo_root,
                    rel_file=rel_file,
                )
                self._emit_import_edge(
                    classification,
                    module_id,
                    alias.name,
                    rel_file,
                    node,
                    repo_ref,
                    snap_ref,
                    now_str,
                    nodes,
                    edges,
                )
        elif isinstance(node, ast.ImportFrom):
            mod_name = node.module or ""
            classification = classify_import(
                module_name=mod_name,
                names=[alias.name for alias in node.names],
                is_relative=node.level > 0,
                level=node.level,
                current_module=current_module,
                repo_root=context.repo_root,
                rel_file=rel_file,
            )
            self._emit_import_edge(
                classification,
                module_id,
                mod_name or ".",
                rel_file,
                node,
                repo_ref,
                snap_ref,
                now_str,
                nodes,
                edges,
            )

    def _emit_import_edge(
        self,
        classification: ImportClassification,
        source_module_id: str,
        import_name: str,
        rel_file: str,
        node: ast.AST,
        repo_ref: RepoRef,
        snap_ref: SnapshotRef,
        now_str: str,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> None:
        if classification.resolution != ImportResolution.resolved_internal:
            return  # Only emit edges for internal imports

        target_path = classification.target_path or import_name
        target_id = make_node_id(
            repo_ref.repo_id,
            "module",
            target_path,
        )
        span = _node_span(node, rel_file)
        prov = parser_provenance(
            repo_ref,
            snap_ref,
            _BACKEND_ID,
            file=rel_file,
            span=span,
            confidence=1.0,
        )
        edges.append(
            GraphEdge(
                edge_id=make_edge_id(
                    repo_ref.repo_id, "imports", source_module_id, target_id
                ),
                edge_type=GraphEdgeType.imports,
                source_id=source_module_id,
                target_id=target_id,
                repo=repo_ref,
                snapshot=snap_ref,
                provenance=prov,
                created_ts=now_str,
            )
        )

    def _process_calls(
        self,
        tree: ast.AST,
        rel_path: str,
        repo_ref: RepoRef,
        snap_ref: SnapshotRef,
        now_str: str,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> None:
        callable_nodes = {
            node.qualified_name: node.node_id
            for node in nodes
            if node.node_type in {GraphNodeType.function, GraphNodeType.method}
            and node.qualified_name
        }
        simple_names = {
            (name.rsplit(".", 1)[-1] if name else ""): node_id
            for name, node_id in callable_nodes.items()
        }

        def walk_defs(body: list[ast.stmt], scope: list[str]) -> None:
            for stmt in body:
                if isinstance(stmt, ast.ClassDef):
                    walk_defs(stmt.body, scope + [stmt.name])
                    continue
                if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                caller_name = _make_qual_name(scope, stmt.name)
                caller_id = callable_nodes.get(caller_name)
                if caller_id is None:
                    continue

                for child in ast.walk(stmt):
                    if not isinstance(child, ast.Call):
                        continue
                    target_name: str | None = None
                    if isinstance(child.func, ast.Name):
                        target_name = child.func.id
                    elif (
                        isinstance(child.func, ast.Attribute)
                        and isinstance(child.func.value, ast.Name)
                        and child.func.value.id == "self"
                    ):
                        target_name = child.func.attr

                    target_id = simple_names.get(target_name or "")
                    if target_id is None or target_id == caller_id:
                        continue

                    span = _node_span(child, rel_path)
                    prov = parser_provenance(
                        repo_ref,
                        snap_ref,
                        _BACKEND_ID,
                        file=rel_path,
                        span=span,
                        confidence=1.0,
                    )
                    edges.append(
                        GraphEdge(
                            edge_id=make_edge_id(
                                repo_ref.repo_id, "calls", caller_id, target_id
                            ),
                            edge_type=GraphEdgeType.calls,
                            source_id=caller_id,
                            target_id=target_id,
                            repo=repo_ref,
                            snapshot=snap_ref,
                            provenance=prov,
                            created_ts=now_str,
                        )
                    )

        if isinstance(tree, ast.Module):
            walk_defs(tree.body, [])
