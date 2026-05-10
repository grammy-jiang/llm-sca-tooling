"""Clean-corpus adapter interface and local fixture adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import orjson

from llm_sca_tooling.sast_repair.models import (
    AlertSpan,
    ClassificationConfidence,
    PredicateExampleRecord,
    RetrievalMethod,
)


class CleanCorpusAdapter(ABC):
    """Interface for clean-corpus adapters."""

    corpus_id: str
    corpus_version: str
    target_repo_id: str | None = None

    @abstractmethod
    def supports_predicate_query(self) -> bool: ...

    @abstractmethod
    def query_by_predicate(
        self, rule_id: str, negated_predicate: str | None
    ) -> list[PredicateExampleRecord]: ...

    @abstractmethod
    def query_by_rule_family(
        self, rule_family: str
    ) -> list[PredicateExampleRecord]: ...

    @abstractmethod
    def query_by_embedding(
        self, embedding: list[float], k: int
    ) -> list[PredicateExampleRecord]: ...


class LocalFixtureCorpusAdapter(CleanCorpusAdapter):
    """Loads pre-curated examples from a local fixtures directory."""

    def __init__(
        self,
        corpus_root: Path,
        *,
        corpus_id: str = "local-fixture",
        corpus_version: str = "0.1.0",
        target_repo_id: str | None = None,
    ) -> None:
        self.corpus_root = Path(corpus_root)
        self.corpus_id = corpus_id
        self.corpus_version = corpus_version
        self.target_repo_id = target_repo_id
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def supports_predicate_query(self) -> bool:
        return True

    def _load(self, rule_id: str) -> list[dict[str, Any]]:
        if rule_id in self._cache:
            return self._cache[rule_id]
        records: list[dict[str, Any]] = []
        for path in sorted(self.corpus_root.glob("*.json")):
            try:
                payload = orjson.loads(path.read_bytes())
            except orjson.JSONDecodeError:
                continue
            for entry in payload if isinstance(payload, list) else []:
                if entry.get("rule_id") == rule_id:
                    records.append(entry)
        self._cache[rule_id] = records
        return records

    def _all_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in sorted(self.corpus_root.glob("*.json")):
            try:
                payload = orjson.loads(path.read_bytes())
            except orjson.JSONDecodeError:
                continue
            if isinstance(payload, list):
                records.extend(payload)
        return records

    def _to_record(
        self, entry: dict[str, Any], retrieval_method: RetrievalMethod
    ) -> PredicateExampleRecord | None:
        if self.target_repo_id and entry.get("repo_id") == self.target_repo_id:
            return None
        span_payload = entry.get("span")
        span = (
            AlertSpan(
                file_path=str(entry.get("file_path", "")),
                start_line=span_payload.get("start_line") if span_payload else None,
                end_line=span_payload.get("end_line") if span_payload else None,
            )
            if span_payload
            else None
        )
        return PredicateExampleRecord(
            rule_id=str(entry["rule_id"]),
            negated_predicate=entry.get("negated_predicate"),
            corpus_id=self.corpus_id,
            example_id=str(entry["example_id"]),
            file_path=str(entry["file_path"]),
            span=span,
            code_snippet=str(entry["code_snippet"]),
            snippet_language=str(entry.get("snippet_language", "text")),
            confidence=ClassificationConfidence(
                entry.get("confidence", ClassificationConfidence.HEURISTIC.value)
            ),
            retrieval_method=retrieval_method,
        )

    def query_by_predicate(
        self, rule_id: str, negated_predicate: str | None
    ) -> list[PredicateExampleRecord]:
        if not negated_predicate:
            return []
        out: list[PredicateExampleRecord] = []
        for entry in self._load(rule_id):
            if entry.get("negated_predicate") == negated_predicate:
                rec = self._to_record(entry, RetrievalMethod.PREDICATE_NEGATION)
                if rec is not None:
                    out.append(rec)
        return out

    def query_by_rule_family(self, rule_family: str) -> list[PredicateExampleRecord]:
        out: list[PredicateExampleRecord] = []
        for entry in self._all_records():
            if str(entry.get("rule_family")) == rule_family:
                rec = self._to_record(entry, RetrievalMethod.RULE_FAMILY_MATCH)
                if rec is not None:
                    out.append(rec)
        return out

    def query_by_embedding(
        self, embedding: list[float], k: int
    ) -> list[PredicateExampleRecord]:
        return []


__all__ = ["CleanCorpusAdapter", "LocalFixtureCorpusAdapter"]
