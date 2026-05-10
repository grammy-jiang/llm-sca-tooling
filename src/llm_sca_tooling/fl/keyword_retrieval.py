"""Deterministic keyword retrieval against graph nodes."""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath
from sqlite3 import Row

from llm_sca_tooling.fl.issue import IssueText
from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    SignalType,
)
from llm_sca_tooling.schemas.enums import GraphNodeType
from llm_sca_tooling.schemas.graph import GraphNode
from llm_sca_tooling.storage.graph_store import GraphStore
from llm_sca_tooling.storage.ids import snapshot_id_for

_SEARCHABLE_TYPES = {
    GraphNodeType.FILE,
    GraphNodeType.MODULE,
    GraphNodeType.CLASS,
    GraphNodeType.FUNCTION,
    GraphNodeType.METHOD,
    GraphNodeType.VARIABLE,
    GraphNodeType.TYPE,
    GraphNodeType.INTERFACE,
    GraphNodeType.IDL_INTERFACE,
    GraphNodeType.HTTP_ROUTE,
    GraphNodeType.WEBSOCKET_EVENT,
    GraphNodeType.DOCUMENT,
    GraphNodeType.DESIGN_CLAUSE,
}
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
}
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")


@dataclass(frozen=True)
class _SearchDocument:
    node: GraphNode
    file_path: str
    text: str
    tokens: list[str]


class KeywordRetriever:
    def __init__(self, graph: GraphStore) -> None:
        self.graph = graph

    def retrieve(
        self,
        issue: IssueText,
        *,
        repo_ids: list[str],
        max_results: int = 50,
        snapshot_id: str | None = None,
    ) -> list[CandidateFile]:
        terms = query_terms(issue)
        if not terms:
            return []
        documents = self._documents(repo_ids, snapshot_id=snapshot_id)
        if not documents:
            return []
        idf = _inverse_document_frequency(documents)
        per_file: dict[tuple[str, str], CandidateFile] = {}
        for document in documents:
            base_score = _bm25_score(terms, document.tokens, idf)
            bonus, bonus_evidence = _stack_trace_bonus(
                issue, document.node, document.file_path
            )
            score = min(1.0, base_score + bonus)
            if score <= 0.0:
                continue
            key = (document.node.repo.repo_id, document.file_path)
            signal = CandidateSignal(
                signal_type=SignalType.KEYWORD,
                raw_score=score,
                evidence=_evidence_text(terms, document, bonus_evidence),
                source_refs=[document.node.node_id],
                confidence=ConfidenceLevel.ANALYSER,
            )
            existing = per_file.get(key)
            candidate = _candidate_from_document(document, signal)
            if (
                existing is None
                or candidate.signals[0].raw_score > existing.signals[0].raw_score
            ):
                per_file[key] = candidate
        return sorted(
            per_file.values(),
            key=lambda candidate: (
                candidate.signals[0].raw_score if candidate.signals else 0.0,
                candidate.file_path,
            ),
            reverse=True,
        )[:max_results]

    def _documents(
        self, repo_ids: list[str], *, snapshot_id: str | None
    ) -> list[_SearchDocument]:
        documents: list[_SearchDocument] = []
        for repo_id in repo_ids:
            for node_type in _SEARCHABLE_TYPES:
                for node in self.graph.fetch_nodes_by_type(
                    repo_id, node_type, snapshot_id=snapshot_id
                ):
                    file_path = _file_path_for_node(node)
                    if not file_path:
                        continue
                    text = _node_text(node)
                    documents.append(
                        _SearchDocument(
                            node=node,
                            file_path=file_path,
                            text=text,
                            tokens=tokenize(text),
                        )
                    )
        return documents


def query_terms(issue: IssueText) -> list[str]:
    weighted_inputs: list[str] = []
    weighted_inputs.extend(issue.error_strings * 3)
    weighted_inputs.extend(issue.mentioned_symbols * 3)
    weighted_inputs.extend(issue.mentioned_files * 4)
    weighted_inputs.extend(issue.mentioned_apis * 3)
    for frame in issue.stack_trace_frames:
        if frame.file_path:
            weighted_inputs.extend([frame.file_path] * 5)
        if frame.function_name:
            weighted_inputs.extend([frame.function_name] * 4)
    weighted_inputs.append(issue.normalized_text)
    return list(
        dict.fromkeys(token for text in weighted_inputs for token in tokenize(text))
    )


def tokenize(text: str) -> list[str]:
    tokens = []
    for match in _TOKEN_RE.finditer(_split_identifier(text)):
        token = _stem(match.group(0).lower())
        if len(token) >= 2 and token not in _STOP_WORDS:
            tokens.append(token)
    return tokens


def _split_identifier(text: str) -> str:
    camel_split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return camel_split.replace("_", " ").replace("-", " ").replace("/", " ")


def _stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _inverse_document_frequency(documents: list[_SearchDocument]) -> dict[str, float]:
    document_frequency: Counter[str] = Counter()
    for document in documents:
        document_frequency.update(set(document.tokens))
    total = len(documents)
    return {
        term: math.log((total - frequency + 0.5) / (frequency + 0.5) + 1.0)
        for term, frequency in document_frequency.items()
    }


def _bm25_score(
    terms: list[str], document_tokens: list[str], idf: dict[str, float]
) -> float:
    if not document_tokens:
        return 0.0
    counts = Counter(document_tokens)
    score = 0.0
    for term in terms:
        frequency = counts.get(term, 0)
        if frequency == 0:
            continue
        score += idf.get(term, 0.0) * ((frequency * 2.2) / (frequency + 1.2))
    return min(1.0, score / (len(set(terms)) + 1.0))


def _stack_trace_bonus(
    issue: IssueText, node: GraphNode, file_path: str
) -> tuple[float, list[str]]:
    bonus = 0.0
    evidence: list[str] = []
    candidate_names = {
        node.label,
        node.qualified_name or "",
        str(node.properties.get("local_name") or ""),
    }
    for mentioned in issue.mentioned_files:
        if _path_matches(mentioned, file_path):
            bonus = max(bonus, 0.5)
            evidence.append(f"file path match {mentioned}")
    for frame in issue.stack_trace_frames:
        if frame.file_path and _path_matches(frame.file_path, file_path):
            bonus = max(bonus, 0.5)
            evidence.append(f"stack frame file {frame.file_path}:{frame.line}")
        if frame.function_name and frame.function_name in candidate_names:
            bonus = max(bonus, 0.4)
            evidence.append(f"stack frame function {frame.function_name}")
    for symbol in issue.mentioned_symbols:
        if symbol in candidate_names:
            bonus = max(bonus, 0.4)
            evidence.append(f"symbol match {symbol}")
    return bonus, evidence


def _path_matches(mentioned: str, file_path: str) -> bool:
    normalized = mentioned.strip("/").replace("\\", "/")
    return (
        normalized == file_path
        or file_path.endswith(normalized)
        or normalized.endswith(file_path)
    )


def _node_text(node: GraphNode) -> str:
    properties = " ".join(_flatten_json(node.properties))
    parts = [
        node.label,
        node.qualified_name or "",
        node.file_path or "",
        PurePosixPath(node.file_path or "").name,
        properties,
    ]
    return " ".join(part for part in parts if part)


def _flatten_json(value: object) -> list[str]:
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            parts.append(str(key))
            parts.extend(_flatten_json(item))
        return parts
    if isinstance(value, list):
        return [part for item in value for part in _flatten_json(item)]
    if value is None:
        return []
    return [str(value)]


def _file_path_for_node(node: GraphNode) -> str | None:
    if node.file_path:
        return node.file_path
    value = node.properties.get("path") or node.properties.get("file_path")
    return str(value) if value else None


def _candidate_from_document(
    document: _SearchDocument, signal: CandidateSignal
) -> CandidateFile:
    snapshot_id = snapshot_id_for(document.node.snapshot)
    return CandidateFile(
        candidate_id=_candidate_id(document.node.repo.repo_id, document.file_path),
        file_path=document.file_path,
        repo_id=document.node.repo.repo_id,
        node_id=document.node.node_id,
        signals=[signal],
        combined_score=signal.raw_score,
        confidence=ConfidenceLevel.ANALYSER,
        evidence_summary=signal.evidence,
        snapshot_id=snapshot_id,
        is_generated=bool(document.node.properties.get("is_generated", False)),
    )


def _candidate_id(repo_id: str, file_path: str) -> str:
    return f"candidate:file:{abs(hash((repo_id, file_path))) & 0xFFFFFFFF:x}"


def _evidence_text(
    terms: list[str], document: _SearchDocument, bonus_evidence: list[str]
) -> str:
    token_counts: defaultdict[str, int] = defaultdict(int)
    for token in document.tokens:
        token_counts[token] += 1
    matched = [term for term in terms if token_counts.get(term, 0) > 0][:5]
    parts = []
    if matched:
        parts.append("keyword terms " + ", ".join(matched))
    parts.extend(bonus_evidence)
    if not parts:
        parts.append(f"keyword match in {document.node.label}")
    return "; ".join(parts)


def row_to_node(row: Row) -> GraphNode:
    return GraphNode.model_validate(json.loads(row["payload_json"]))
