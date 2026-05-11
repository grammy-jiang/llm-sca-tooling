"""Deterministic graph lookup for repo-QA."""

from __future__ import annotations

import re
from typing import Any

from pydantic import Field
from sqlalchemy import text

from llm_sca_tooling.qa.question import QuestionClass, RepoQuestion, StrictQaModel
from llm_sca_tooling.schemas.graph import GraphNode, GraphNodeType
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = ["GraphNodeRef", "LookupResult", "lookup_files", "lookup_symbols"]


class GraphNodeRef(StrictQaModel):
    node_id: str
    node_type: str
    repo_id: str
    file_path: str | None = None
    span: dict[str, Any] | None = None
    symbol_path: str | None = None
    confidence: str = "heuristic"
    source: str


class LookupResult(StrictQaModel):
    question_class: QuestionClass
    matched_nodes: list[GraphNodeRef] = Field(default_factory=list)
    lookup_strategy: str
    confidence: str
    diagnostics: list[str] = Field(default_factory=list)


async def lookup_files(
    workspace: WorkspaceStore, question: RepoQuestion, repo_ids: list[str] | None = None
) -> LookupResult:
    nodes = await _candidate_nodes(workspace, repo_ids)
    refs: list[GraphNodeRef] = []
    for hint in question.file_hints:
        refs.extend(
            _ref(node, "parser", "exact_path")
            for node in nodes
            if node.file_path and node.file_path.endswith(hint)
        )
    if not refs:
        for token in question.code_tokens:
            refs.extend(
                _ref(node, "parser", "symbol_to_file")
                for node in nodes
                if _node_matches(node, token) and node.file_path
            )
    if not refs:
        words = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]+", question.normalized_text))
        refs.extend(
            _ref(node, "analyser", "keyword")
            for node in nodes
            if node.file_path and PathName(node.file_path).stem.lower() in words
        )
    confidence = refs[0].confidence if refs else "unknown"
    return LookupResult(
        question_class=QuestionClass.file_loc,
        matched_nodes=_dedupe(refs),
        lookup_strategy=refs[0].source if refs else "no_match",
        confidence=confidence,
        diagnostics=[] if refs else ["NO_FILE_MATCH"],
    )


async def lookup_symbols(
    workspace: WorkspaceStore, question: RepoQuestion, repo_ids: list[str] | None = None
) -> LookupResult:
    nodes = await _candidate_nodes(workspace, repo_ids)
    refs: list[GraphNodeRef] = []
    for token in question.code_tokens or question.normalized_text.split():
        refs.extend(
            _ref(node, "parser", "exact_symbol")
            for node in nodes
            if node.node_type in _SYMBOL_TYPES and _node_matches(node, token)
        )
    if not refs:
        compact = re.sub(r"[^a-z0-9]", "", question.normalized_text.lower())
        refs.extend(
            _ref(node, "analyser", "fuzzy_symbol")
            for node in nodes
            if node.node_type in _SYMBOL_TYPES
            and re.sub(r"[^a-z0-9]", "", node.label.lower()) in compact
        )
    confidence = refs[0].confidence if refs else "unknown"
    return LookupResult(
        question_class=QuestionClass.symbol_loc,
        matched_nodes=_dedupe(refs),
        lookup_strategy=refs[0].source if refs else "no_match",
        confidence=confidence,
        diagnostics=[] if refs else ["NO_SYMBOL_MATCH"],
    )


_SYMBOL_TYPES = {GraphNodeType.function, GraphNodeType.method, GraphNodeType.class_}


class PathName(str):
    @property
    def stem(self) -> str:
        return self.rsplit("/", 1)[-1].split(".", 1)[0]


async def _candidate_nodes(
    workspace: WorkspaceStore, repo_ids: list[str] | None
) -> list[GraphNode]:
    async with workspace._session_factory() as session:
        rows = (
            await session.execute(text("SELECT payload_json FROM graph_nodes"))
        ).all()
    nodes = [GraphNode.model_validate_json(str(row[0])) for row in rows]
    return [node for node in nodes if not repo_ids or node.repo.repo_id in repo_ids]


def _node_matches(node: GraphNode, token: str) -> bool:
    return token in {node.label, node.qualified_name, node.file_path}


def _ref(node: GraphNode, confidence: str, source: str) -> GraphNodeRef:
    return GraphNodeRef(
        node_id=node.node_id,
        node_type=node.node_type.value,
        repo_id=node.repo.repo_id,
        file_path=node.file_path,
        span=node.span.model_dump(mode="json") if node.span else None,
        symbol_path=node.qualified_name or node.label,
        confidence=confidence,
        source=source,
    )


def _dedupe(refs: list[GraphNodeRef]) -> list[GraphNodeRef]:
    seen: set[str] = set()
    deduped: list[GraphNodeRef] = []
    for ref in refs:
        if ref.node_id in seen:
            continue
        seen.add(ref.node_id)
        deduped.append(ref)
    return deduped
