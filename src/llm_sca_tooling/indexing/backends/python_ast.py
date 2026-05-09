"""Python AST indexing backend."""

from __future__ import annotations

import ast
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import BackendCapabilities, BackendResult
from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.indexing.scanner import (
    ScannedFile,
    edge_id,
    module_name_for_path,
    node_id,
)
from llm_sca_tooling.schemas.enums import (
    DerivationType,
    EvidenceStrength,
    GraphEdgeType,
    GraphNodeType,
    Severity,
)
from llm_sca_tooling.schemas.graph import GraphEdge, GraphNode
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef, SourceSpan
from llm_sca_tooling.storage.workspace import _now_ts


class PythonAstBackend:
    backend_id = "python-ast"

    def backend_version(self) -> str:
        return "stdlib-ast"

    def supported_languages(self) -> list[str]:
        return ["python"]

    def detect_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            backend_id=self.backend_id,
            installed=True,
            version=self.backend_version(),
            supported_languages=["python"],
            supported_node_types=["module", "class", "function", "method", "test"],
            supported_edge_types=["contains", "imports", "calls", "tests"],
            known_limitations=["Conservative same-module call detection only"],
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
        started = _now_ts()
        result = BackendResult(
            backend_id=self.backend_id,
            backend_version=self.backend_version(),
            started_ts=started,
            ended_ts=started,
        )
        python_files = [file for file in files if file.language == "python"]
        module_nodes = {
            module_name_for_path(file.path): self._module_node(
                repo, snapshot, file, run_id=run_id
            )
            for file in python_files
        }
        known_symbols: dict[str, GraphNode] = {}
        by_simple_name: dict[str, list[GraphNode]] = {}
        for file in python_files:
            try:
                tree = ast.parse(
                    file.abs_path.read_text(encoding="utf-8"), filename=file.path
                )
            except (SyntaxError, UnicodeDecodeError) as exc:
                result.files_skipped.append(file.path)
                result.diagnostics.append(
                    IndexDiagnostic(
                        diagnostic_id=f"diag:python-ast:{file.sha256[:12]}",
                        severity=Severity.WARNING,
                        code="python_parse_failed",
                        message=str(exc),
                        file_path=file.path,
                    )
                )
                continue
            result.files_processed.append(file.path)
            module_node = module_nodes[module_name_for_path(file.path)]
            result.nodes.append(module_node)
            symbols, contains_edges = self._symbols_for_tree(
                repo, snapshot, file, module_node, tree, run_id=run_id
            )
            result.nodes.extend(symbols)
            result.edges.extend(contains_edges)
            for symbol in symbols:
                if symbol.qualified_name:
                    known_symbols[symbol.qualified_name] = symbol
                    by_simple_name.setdefault(
                        symbol.qualified_name.rsplit(".", 1)[-1].split(":")[-1], []
                    ).append(symbol)
            result.edges.extend(
                self._import_edges(
                    repo,
                    snapshot,
                    file,
                    module_node,
                    tree,
                    module_nodes,
                    run_id=run_id,
                    diagnostics=result.diagnostics,
                )
            )
            result.edges.extend(
                self._call_edges(repo, snapshot, file, tree, symbols, run_id=run_id)
            )
        for symbol in [
            node
            for node in known_symbols.values()
            if node.node_type == GraphNodeType.TEST
        ]:
            target_name = symbol.qualified_name.rsplit(":", 1)[-1].removeprefix("test_")
            candidates = by_simple_name.get(target_name, [])
            if len(candidates) == 1:
                result.edges.append(
                    self._edge(
                        repo,
                        snapshot,
                        GraphEdgeType.TESTS,
                        symbol.node_id,
                        candidates[0].node_id,
                        run_id=run_id,
                        confidence=0.7,
                        derivation=DerivationType.HEURISTIC,
                    )
                )
        result.ended_ts = _now_ts()
        return result

    def _module_node(
        self,
        repo: RepoRef,
        snapshot: SnapshotRef,
        file: ScannedFile,
        *,
        run_id: str | None,
    ) -> GraphNode:
        provenance = make_provenance(
            source_tool="evidence-sca.python-ast",
            repo=repo,
            snapshot=snapshot,
            source_run_id=run_id,
            file=file.path,
        )
        module_name = module_name_for_path(file.path)
        return GraphNode(
            node_id=node_id(repo.repo_id, snapshot, GraphNodeType.MODULE, file.path),
            node_type=GraphNodeType.MODULE,
            label=module_name,
            qualified_name=module_name,
            repo=repo,
            snapshot=snapshot,
            file_path=file.path,
            provenance=provenance,
            properties={
                "language": "python",
                "sha256": file.sha256,
                "is_test": file.is_test,
            },
            created_ts=_now_ts(),
        )

    def _symbols_for_tree(
        self,
        repo: RepoRef,
        snapshot: SnapshotRef,
        file: ScannedFile,
        module_node: GraphNode,
        tree: ast.Module,
        *,
        run_id: str | None,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        def visit_body(
            body: list[ast.stmt],
            parent_node: GraphNode,
            scope: list[str],
            current_class: str | None = None,
        ) -> None:
            for item in body:
                if isinstance(item, ast.ClassDef):
                    qname = (
                        f"{module_node.qualified_name}:{'.'.join(scope + [item.name])}"
                        if scope
                        else f"{module_node.qualified_name}:{item.name}"
                    )
                    node = self._symbol_node(
                        repo,
                        snapshot,
                        file,
                        item,
                        GraphNodeType.CLASS,
                        qname,
                        run_id=run_id,
                    )
                    nodes.append(node)
                    edges.append(
                        self._edge(
                            repo,
                            snapshot,
                            GraphEdgeType.CONTAINS,
                            parent_node.node_id,
                            node.node_id,
                            run_id=run_id,
                        )
                    )
                    visit_body(
                        item.body, node, scope + [item.name], current_class=item.name
                    )
                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    is_method = current_class is not None
                    is_test = item.name.startswith("test_") or (
                        current_class or ""
                    ).startswith("Test")
                    ntype = (
                        GraphNodeType.TEST
                        if is_test
                        else (
                            GraphNodeType.METHOD
                            if is_method
                            else GraphNodeType.FUNCTION
                        )
                    )
                    qname = (
                        f"{module_node.qualified_name}:{'.'.join(scope + [item.name])}"
                        if scope
                        else f"{module_node.qualified_name}:{item.name}"
                    )
                    node = self._symbol_node(
                        repo, snapshot, file, item, ntype, qname, run_id=run_id
                    )
                    nodes.append(node)
                    edges.append(
                        self._edge(
                            repo,
                            snapshot,
                            GraphEdgeType.CONTAINS,
                            parent_node.node_id,
                            node.node_id,
                            run_id=run_id,
                        )
                    )
                    visit_body(
                        item.body,
                        node,
                        scope + [item.name],
                        current_class=current_class,
                    )

        visit_body(tree.body, module_node, [])
        return nodes, edges

    def _symbol_node(
        self,
        repo: RepoRef,
        snapshot: SnapshotRef,
        file: ScannedFile,
        item: ast.AST,
        node_type: GraphNodeType,
        qname: str,
        *,
        run_id: str | None,
    ) -> GraphNode:
        line = getattr(item, "lineno", 1)
        end_line = getattr(item, "end_lineno", line)
        span = SourceSpan(
            file_path=file.path,
            start_line=line,
            start_col=getattr(item, "col_offset", 0) + 1,
            end_line=end_line,
            end_col=None,
        )
        provenance = make_provenance(
            source_tool="evidence-sca.python-ast",
            repo=repo,
            snapshot=snapshot,
            source_run_id=run_id,
            file=file.path,
            span=span,
        )
        return GraphNode(
            node_id=node_id(
                repo.repo_id, snapshot, node_type, f"{qname}:{line}:{end_line}"
            ),
            node_type=node_type,
            label=qname.rsplit(":", 1)[-1],
            qualified_name=qname,
            repo=repo,
            snapshot=snapshot,
            file_path=file.path,
            span=span,
            provenance=provenance,
            properties={
                "language": "python",
                "decorators": decorators(item),
                "is_test": node_type == GraphNodeType.TEST,
            },
            created_ts=_now_ts(),
        )

    def _import_edges(
        self,
        repo: RepoRef,
        snapshot: SnapshotRef,
        file: ScannedFile,
        module_node: GraphNode,
        tree: ast.Module,
        module_nodes: dict[str, GraphNode],
        *,
        run_id: str | None,
        diagnostics: list[IndexDiagnostic],
    ) -> list[GraphEdge]:
        edges: list[GraphEdge] = []
        current_module = module_name_for_path(file.path)
        for item in ast.walk(tree):
            module_name: str | None = None
            if isinstance(item, ast.Import):
                for alias in item.names:
                    module_name = alias.name
                    edges.extend(
                        self._resolve_import(
                            repo,
                            snapshot,
                            module_node,
                            module_name,
                            module_nodes,
                            run_id=run_id,
                            diagnostics=diagnostics,
                            file_path=file.path,
                        )
                    )
            elif isinstance(item, ast.ImportFrom):
                module_name = resolve_from_import(current_module, item)
                edges.extend(
                    self._resolve_import(
                        repo,
                        snapshot,
                        module_node,
                        module_name,
                        module_nodes,
                        run_id=run_id,
                        diagnostics=diagnostics,
                        file_path=file.path,
                    )
                )
        return edges

    def _resolve_import(
        self,
        repo: RepoRef,
        snapshot: SnapshotRef,
        source: GraphNode,
        module_name: str | None,
        module_nodes: dict[str, GraphNode],
        *,
        run_id: str | None,
        diagnostics: list[IndexDiagnostic],
        file_path: str,
    ) -> list[GraphEdge]:
        if not module_name:
            return []
        candidates = [
            name
            for name in module_nodes
            if name == module_name or name.startswith(f"{module_name}.")
        ]
        if not candidates:
            diagnostics.append(
                IndexDiagnostic(
                    diagnostic_id=f"diag:import:{hash(module_name)}",
                    severity=Severity.INFO,
                    code="external_or_unresolved_import",
                    message=f"Import not resolved internally: {module_name}",
                    file_path=file_path,
                    details={"module": module_name},
                )
            )
            return []
        if len(candidates) > 1 and module_name not in module_nodes:
            diagnostics.append(
                IndexDiagnostic(
                    diagnostic_id=f"diag:import-ambiguous:{hash(module_name)}",
                    severity=Severity.WARNING,
                    code="ambiguous_import",
                    message=f"Ambiguous import: {module_name}",
                    file_path=file_path,
                )
            )
            return []
        target = module_nodes[
            module_name if module_name in module_nodes else candidates[0]
        ]
        return [
            self._edge(
                repo,
                snapshot,
                GraphEdgeType.IMPORTS,
                source.node_id,
                target.node_id,
                run_id=run_id,
            )
        ]

    def _call_edges(
        self,
        repo: RepoRef,
        snapshot: SnapshotRef,
        file: ScannedFile,
        tree: ast.Module,
        symbols: list[GraphNode],
        *,
        run_id: str | None,
    ) -> list[GraphEdge]:
        functions = {
            symbol.qualified_name.rsplit(":", 1)[-1].split(".")[-1]: symbol
            for symbol in symbols
            if symbol.node_type in {GraphNodeType.FUNCTION, GraphNodeType.METHOD}
        }
        edges: list[GraphEdge] = []
        for call in [node for node in ast.walk(tree) if isinstance(node, ast.Call)]:
            name = call_name(call)
            if name and name in functions:
                caller = enclosing_symbol(call, symbols)
                if caller and caller.node_id != functions[name].node_id:
                    edges.append(
                        self._edge(
                            repo,
                            snapshot,
                            GraphEdgeType.CALLS,
                            caller.node_id,
                            functions[name].node_id,
                            run_id=run_id,
                            confidence=0.9,
                        )
                    )
        return edges

    def _edge(
        self,
        repo: RepoRef,
        snapshot: SnapshotRef,
        edge_type: GraphEdgeType,
        source_id: str,
        target_id: str,
        *,
        run_id: str | None,
        confidence: float = 1.0,
        derivation: DerivationType = DerivationType.PARSER,
    ) -> GraphEdge:
        strength = (
            EvidenceStrength.HARD_STATIC
            if derivation == DerivationType.PARSER
            else EvidenceStrength.STRUCTURED_REPOSITORY
        )
        provenance = make_provenance(
            source_tool="evidence-sca.python-ast",
            repo=repo,
            snapshot=snapshot,
            source_run_id=run_id,
            derivation=derivation,
            evidence_strength=strength,
            confidence=confidence,
        )
        return GraphEdge(
            edge_id=edge_id(repo.repo_id, snapshot, edge_type, source_id, target_id),
            edge_type=edge_type,
            source_id=source_id,
            target_id=target_id,
            repo=repo,
            snapshot=snapshot,
            provenance=provenance,
            confidence=confidence,
            properties={},
            created_ts=_now_ts(),
        )


def decorators(item: ast.AST) -> list[str]:
    return [ast.unparse(decorator) for decorator in getattr(item, "decorator_list", [])]


def resolve_from_import(current_module: str, item: ast.ImportFrom) -> str | None:
    base_parts = current_module.split(".")[: -item.level] if item.level else []
    if item.level == 0:
        base = item.module or ""
    else:
        base = ".".join(base_parts + ([item.module] if item.module else []))
    if base:
        return base
    if item.names:
        return ".".join(base_parts + [item.names[0].name])
    return None


def call_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def enclosing_symbol(call: ast.Call, symbols: list[GraphNode]) -> GraphNode | None:
    line = getattr(call, "lineno", 0)
    candidates = [
        symbol
        for symbol in symbols
        if symbol.span and symbol.span.start_line <= line <= symbol.span.end_line
    ]
    return (
        sorted(
            candidates,
            key=lambda symbol: (
                symbol.span.end_line - symbol.span.start_line if symbol.span else 9999
            ),
        )[0]
        if candidates
        else None
    )
