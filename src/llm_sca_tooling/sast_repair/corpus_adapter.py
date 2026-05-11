"""Local clean-corpus adapter."""

from __future__ import annotations

from pathlib import Path

import orjson

from llm_sca_tooling.sast_repair.models import PredicateExampleRecord


class LocalFixtureCorpusAdapter:
    corpus_id = "local-fixture"
    corpus_version = "phase12.v1"

    def __init__(self, root: Path | None = None) -> None:
        self.root = root

    def supports_predicate_query(self) -> bool:
        return True

    def query_by_predicate(
        self, rule_id: str, negated_predicate: str | None
    ) -> list[PredicateExampleRecord]:
        if negated_predicate is None:
            return []
        examples = self._load_examples()
        return [
            example.model_copy(update={"retrieval_method": "predicate_negation"})
            for example in examples
            if example.rule_id == rule_id
            and example.negated_predicate == negated_predicate
        ]

    def query_by_rule_family(self, rule_family: str) -> list[PredicateExampleRecord]:
        examples = self._load_examples()
        return [
            example.model_copy(update={"retrieval_method": "rule_family_match"})
            for example in examples
            if rule_family in example.rule_id.lower()
        ]

    def query_by_embedding(
        self, embedding: list[float], k: int
    ) -> list[PredicateExampleRecord]:
        return []

    def _load_examples(self) -> list[PredicateExampleRecord]:
        if self.root is not None and self.root.exists():
            loaded: list[PredicateExampleRecord] = []
            for path in sorted(self.root.glob("*.json")):
                for row in orjson.loads(path.read_bytes()):
                    loaded.append(PredicateExampleRecord.model_validate(row))
            return loaded
        return [
            PredicateExampleRecord(
                rule_id="NULL_DEREF",
                negated_predicate="value is checked for null before dereference",
                corpus_id=self.corpus_id,
                example_id="null-guard",
                file_path="clean/null_guard.py",
                span=(1, 3),
                code_snippet="if value is None:\n    return None\nreturn value.name",
                snippet_language="python",
                confidence="analyser",
                retrieval_method="predicate_negation",
                repo_id="clean-corpus",
            ),
            PredicateExampleRecord(
                rule_id="CWE-89",
                negated_predicate="input is validated or parameterized before the sink",
                corpus_id=self.corpus_id,
                example_id="parameterized-query",
                file_path="clean/sql.py",
                span=(1, 2),
                code_snippet=(
                    "cursor.execute('select * from users where id=?', [user_id])"
                ),
                snippet_language="python",
                confidence="analyser",
                retrieval_method="predicate_negation",
                repo_id="clean-corpus",
            ),
        ]
