"""Deterministic file and symbol lookup against the graph store."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from pydantic import Field

from llm_sca_tooling.qa.confidence import ConfidenceLabel
from llm_sca_tooling.qa.question import QuestionClass, RepoQuestion
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType
from llm_sca_tooling.schemas.graph import GraphNode
from llm_sca_tooling.schemas.provenance import SourceSpan
from llm_sca_tooling.storage.graph_store import GraphStore


class GraphNodeRef(StrictBaseModel):
    node_id: str
    node_type: str
    file_path: str | None = None
    span: SourceSpan | None = None
    symbol_path: str | None = None
    confidence: ConfidenceLabel
    source: str
    repo_id: str | None = None


class LookupResult(StrictBaseModel):
    question_class: QuestionClass
    matched_nodes: list[GraphNodeRef] = Field(default_factory=list)
    lookup_strategy: str
    confidence: ConfidenceLabel
    diagnostics: list[str] = Field(default_factory=list)


def node_ref(node: GraphNode, confidence: ConfidenceLabel, source: str) -> GraphNodeRef:
    return GraphNodeRef(
        node_id=node.node_id,
        node_type=node.node_type.value,
        file_path=node.file_path,
        span=node.span,
        symbol_path=node.qualified_name or node.properties.get("local_name"),
        confidence=confidence,
        source=source,
        repo_id=node.repo.repo_id,
    )


class FileLocLookup:
    def __init__(self, graph_store: GraphStore) -> None:
        self.graph = graph_store

    def lookup(
        self,
        question: RepoQuestion,
        repo_ids: list[str],
        *,
        snapshot_id: str | None = None,
    ) -> LookupResult:
        diagnostics: list[str] = []
        for strategy in (
            self._exact_path,
            self._module_name,
            self._symbol_to_file,
            self._keyword_file_name,
            self._build_evidence_hint,
        ):
            refs = strategy(question, repo_ids, snapshot_id)
            if refs:
                return LookupResult(
                    question_class=QuestionClass.FILE_LOC,
                    matched_nodes=refs,
                    lookup_strategy=refs[0].source,
                    confidence=refs[0].confidence,
                    diagnostics=diagnostics,
                )
        diagnostics.append("no_file_match")
        return LookupResult(
            question_class=QuestionClass.FILE_LOC,
            matched_nodes=[],
            lookup_strategy="none",
            confidence=ConfidenceLabel.UNKNOWN,
            diagnostics=diagnostics,
        )

    def _exact_path(
        self, question: RepoQuestion, repo_ids: list[str], snapshot_id: str | None
    ) -> list[GraphNodeRef]:
        refs = []
        for repo_id in repo_ids:
            for hint in question.file_hints:
                rows = self.graph.conn.execute(
                    "SELECT payload_json FROM graph_nodes WHERE repo_id=? AND node_type=? AND (file_path=? OR file_path LIKE ?) "
                    + ("AND snapshot_id=?" if snapshot_id else ""),
                    (
                        repo_id,
                        GraphNodeType.FILE.value,
                        hint,
                        f"%/{hint}",
                        *([snapshot_id] if snapshot_id else []),
                    ),
                ).fetchall()
                refs.extend(
                    node_ref(
                        GraphNode.model_validate_json(row["payload_json"]),
                        ConfidenceLabel.PARSER,
                        "exact_path",
                    )
                    for row in rows
                )
        return _dedupe(refs)

    def _module_name(
        self, question: RepoQuestion, repo_ids: list[str], snapshot_id: str | None
    ) -> list[GraphNodeRef]:
        tokens = _candidate_tokens(question)
        refs = []
        for repo_id in repo_ids:
            for token in tokens:
                rows = self.graph.conn.execute(
                    "SELECT payload_json FROM graph_nodes WHERE repo_id=? AND node_type=? AND (qualified_name=? OR label=?) "
                    + ("AND snapshot_id=?" if snapshot_id else ""),
                    (
                        repo_id,
                        GraphNodeType.MODULE.value,
                        token,
                        token,
                        *([snapshot_id] if snapshot_id else []),
                    ),
                ).fetchall()
                refs.extend(
                    node_ref(
                        GraphNode.model_validate_json(row["payload_json"]),
                        ConfidenceLabel.PARSER,
                        "module_name",
                    )
                    for row in rows
                )
        return _dedupe(refs)

    def _symbol_to_file(
        self, question: RepoQuestion, repo_ids: list[str], snapshot_id: str | None
    ) -> list[GraphNodeRef]:
        symbols = SymbolLocLookup(self.graph).lookup(
            question, repo_ids, snapshot_id=snapshot_id, expand_interfaces=False
        )
        refs = []
        for symbol in symbols.matched_nodes:
            if symbol.file_path:
                file_node = _file_node_for_path(
                    self.graph, symbol.repo_id or "", symbol.file_path, snapshot_id
                )
                refs.append(
                    node_ref(file_node, symbol.confidence, "symbol_to_file")
                    if file_node
                    else symbol
                )
        return _dedupe(refs)

    def _keyword_file_name(
        self, question: RepoQuestion, repo_ids: list[str], snapshot_id: str | None
    ) -> list[GraphNodeRef]:
        tokens = {
            token.lower() for token in _candidate_tokens(question) if len(token) >= 3
        }
        refs = []
        for repo_id in repo_ids:
            rows = self.graph.conn.execute(
                "SELECT payload_json FROM graph_nodes WHERE repo_id=? AND node_type=? "
                + ("AND snapshot_id=?" if snapshot_id else ""),
                (
                    repo_id,
                    GraphNodeType.FILE.value,
                    *([snapshot_id] if snapshot_id else []),
                ),
            ).fetchall()
            for row in rows:
                node = GraphNode.model_validate_json(row["payload_json"])
                basename = PurePosixPath(node.file_path or node.label).stem.lower()
                if basename in tokens or any(token in basename for token in tokens):
                    refs.append(node_ref(node, ConfidenceLabel.ANALYSER, "keyword"))
        return _dedupe(refs)

    def _build_evidence_hint(
        self, question: RepoQuestion, repo_ids: list[str], snapshot_id: str | None
    ) -> list[GraphNodeRef]:
        if not any(
            token in question.normalized_text for token in ("test", "ci", "build")
        ):
            return []
        refs = []
        for repo_id in repo_ids:
            for node_type in (
                GraphNodeType.CI_JOB,
                GraphNodeType.BUILD_TARGET,
                GraphNodeType.TEST,
            ):
                refs.extend(
                    node_ref(node, ConfidenceLabel.HEURISTIC, "build_evidence")
                    for node in self.graph.fetch_nodes_by_type(
                        repo_id, node_type, snapshot_id=snapshot_id
                    )
                )
        return _dedupe(refs)


class SymbolLocLookup:
    def __init__(self, graph_store: GraphStore) -> None:
        self.graph = graph_store

    def lookup(
        self,
        question: RepoQuestion,
        repo_ids: list[str],
        *,
        snapshot_id: str | None = None,
        expand_interfaces: bool = True,
    ) -> LookupResult:
        for strategy in (self._exact_symbol, self._qualified_name, self._fuzzy_symbol):
            refs = strategy(question, repo_ids, snapshot_id)
            if refs:
                if expand_interfaces:
                    refs = _dedupe(refs + self._interface_expansion(refs))
                return LookupResult(
                    question_class=QuestionClass.SYMBOL_LOC,
                    matched_nodes=refs,
                    lookup_strategy=refs[0].source,
                    confidence=refs[0].confidence,
                    diagnostics=[],
                )
        return LookupResult(
            question_class=QuestionClass.SYMBOL_LOC,
            matched_nodes=[],
            lookup_strategy="none",
            confidence=ConfidenceLabel.UNKNOWN,
            diagnostics=["symbol_not_found"],
        )

    def _exact_symbol(
        self, question: RepoQuestion, repo_ids: list[str], snapshot_id: str | None
    ) -> list[GraphNodeRef]:
        refs = []
        for repo_id in repo_ids:
            for token in _candidate_tokens(question):
                rows = self.graph.conn.execute(
                    "SELECT payload_json FROM graph_nodes WHERE repo_id=? AND node_type IN ('class','function','method','interface') AND (qualified_name=? OR label=? OR json_extract(payload_json, '$.properties.local_name')=?) "
                    + ("AND snapshot_id=?" if snapshot_id else ""),
                    (
                        repo_id,
                        token,
                        token,
                        token,
                        *([snapshot_id] if snapshot_id else []),
                    ),
                ).fetchall()
                refs.extend(
                    node_ref(
                        GraphNode.model_validate_json(row["payload_json"]),
                        ConfidenceLabel.PARSER,
                        "exact_symbol",
                    )
                    for row in rows
                )
        return _dedupe(refs)

    def _qualified_name(
        self, question: RepoQuestion, repo_ids: list[str], snapshot_id: str | None
    ) -> list[GraphNodeRef]:
        return self._exact_symbol(question, repo_ids, snapshot_id)

    def _fuzzy_symbol(
        self, question: RepoQuestion, repo_ids: list[str], snapshot_id: str | None
    ) -> list[GraphNodeRef]:
        wanted = {
            _fuzzy_key(token)
            for token in _candidate_tokens(question)
            if len(token) >= 3
        }
        refs = []
        for repo_id in repo_ids:
            rows = self.graph.conn.execute(
                "SELECT payload_json FROM graph_nodes WHERE repo_id=? AND node_type IN ('class','function','method','interface') "
                + ("AND snapshot_id=?" if snapshot_id else ""),
                (repo_id, *([snapshot_id] if snapshot_id else [])),
            ).fetchall()
            for row in rows:
                node = GraphNode.model_validate_json(row["payload_json"])
                names = [
                    node.qualified_name or "",
                    node.label,
                    str(node.properties.get("local_name") or ""),
                ]
                if any(_fuzzy_key(name) in wanted for name in names):
                    refs.append(
                        node_ref(node, ConfidenceLabel.ANALYSER, "fuzzy_symbol")
                    )
        return _dedupe(refs)

    def _interface_expansion(self, refs: list[GraphNodeRef]) -> list[GraphNodeRef]:
        expanded = []
        edge_types = {
            GraphEdgeType.EXPOSES.value,
            GraphEdgeType.CONSUMES.value,
            GraphEdgeType.IMPLEMENTS.value,
            GraphEdgeType.FFI.value,
        }
        for ref in refs:
            rows = self.graph.conn.execute(
                f"SELECT source_id, target_id FROM graph_edges WHERE (source_id=? OR target_id=?) AND edge_type IN ({','.join('?' for _ in edge_types)})",
                (ref.node_id, ref.node_id, *edge_types),
            ).fetchall()
            for row in rows:
                other_id = (
                    row["target_id"]
                    if row["source_id"] == ref.node_id
                    else row["source_id"]
                )
                node = self.graph.fetch_node(other_id)
                if node:
                    expanded.append(
                        node_ref(node, ref.confidence, "interface_expansion")
                    )
        return expanded


def _candidate_tokens(question: RepoQuestion) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_.-]*", question.normalized_text)
    stop = {
        "where",
        "which",
        "what",
        "file",
        "function",
        "class",
        "method",
        "handles",
        "handle",
        "implemented",
        "defined",
        "the",
        "does",
        "is",
        "in",
        "for",
        "logic",
        "contains",
    }
    return [
        token
        for token in question.code_tokens + question.file_hints + words
        if token.lower() not in stop
    ]


def _fuzzy_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value).lower()


def _file_node_for_path(
    graph: GraphStore, repo_id: str, file_path: str, snapshot_id: str | None
) -> GraphNode | None:
    rows = graph.conn.execute(
        "SELECT payload_json FROM graph_nodes WHERE repo_id=? AND node_type=? AND file_path=? "
        + ("AND snapshot_id=?" if snapshot_id else "")
        + " LIMIT 1",
        (
            repo_id,
            GraphNodeType.FILE.value,
            file_path,
            *([snapshot_id] if snapshot_id else []),
        ),
    ).fetchall()
    return GraphNode.model_validate_json(rows[0]["payload_json"]) if rows else None


def _dedupe(refs: list[GraphNodeRef]) -> list[GraphNodeRef]:
    seen: set[str] = set()
    result = []
    for ref in refs:
        if ref.node_id in seen:
            continue
        seen.add(ref.node_id)
        result.append(ref)
    return result
