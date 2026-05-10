"""Tests for the local-fixture corpus adapter and predicate-example retrieval."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.sast_repair.corpus_adapter import LocalFixtureCorpusAdapter
from llm_sca_tooling.sast_repair.models import RetrievalMethod
from llm_sca_tooling.sast_repair.predicate_examples import get_predicate_examples
from llm_sca_tooling.sast_repair.predicate_metadata import extract_predicate_metadata


def test_adapter_predicate_negation(corpus_root: Path) -> None:
    adapter = LocalFixtureCorpusAdapter(corpus_root)
    examples = adapter.query_by_predicate(
        "py.nullderef", "expression guarded by a None check before dereference"
    )
    assert examples, "expected predicate-negation matches"
    assert all(
        e.retrieval_method is RetrievalMethod.PREDICATE_NEGATION for e in examples
    )


def test_adapter_predicate_query_no_predicate(corpus_root: Path) -> None:
    adapter = LocalFixtureCorpusAdapter(corpus_root)
    assert adapter.query_by_predicate("py.nullderef", None) == []


def test_adapter_rule_family(corpus_root: Path) -> None:
    adapter = LocalFixtureCorpusAdapter(corpus_root)
    examples = adapter.query_by_rule_family("injection")
    assert examples
    assert examples[0].retrieval_method is RetrievalMethod.RULE_FAMILY_MATCH


def test_adapter_excludes_target_repo(corpus_root: Path, tmp_path: Path) -> None:
    repo_corpus = tmp_path / "corpus"
    repo_corpus.mkdir()
    (repo_corpus / "x.json").write_text(
        '[{"rule_id": "r", "rule_family": "f", "negated_predicate": "p", '
        '"corpus_id": "c", "example_id": "e1", "file_path": "p.py", '
        '"code_snippet": "x", "repo_id": "blocked"}]',
        encoding="utf-8",
    )
    adapter = LocalFixtureCorpusAdapter(repo_corpus, target_repo_id="blocked")
    assert adapter.query_by_predicate("r", "p") == []


def test_adapter_query_embedding_returns_empty(corpus_root: Path) -> None:
    adapter = LocalFixtureCorpusAdapter(corpus_root)
    assert adapter.query_by_embedding([0.1, 0.2], k=5) == []


def test_adapter_skips_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not-json", encoding="utf-8")
    adapter = LocalFixtureCorpusAdapter(tmp_path)
    assert adapter.query_by_rule_family("anything") == []


def test_get_predicate_examples_predicate_negation(corpus_root: Path) -> None:
    metadata = extract_predicate_metadata(rule_id="py.nullderef")
    adapter = LocalFixtureCorpusAdapter(corpus_root)
    examples, diagnostics = get_predicate_examples(
        metadata=metadata, adapter=adapter, k=5
    )
    assert examples
    assert any(d["code"] == "corpus_freshness" for d in diagnostics)


def test_get_predicate_examples_family_fallback(corpus_root: Path) -> None:
    metadata = extract_predicate_metadata(rule_id="py.nullderef")
    metadata = metadata.model_copy(update={"negated_predicate_text": "no-match"})
    adapter = LocalFixtureCorpusAdapter(corpus_root)
    examples, diagnostics = get_predicate_examples(
        metadata=metadata, adapter=adapter, k=5
    )
    assert examples
    assert any(d["code"] == "rule_family_fallback" for d in diagnostics)


def test_get_predicate_examples_no_results_emits_diagnostic(corpus_root: Path) -> None:
    metadata = extract_predicate_metadata(rule_id="py.nullderef")
    metadata = metadata.model_copy(
        update={"negated_predicate_text": None, "rule_family": "no-such-family"}
    )
    adapter = LocalFixtureCorpusAdapter(corpus_root)
    examples, diagnostics = get_predicate_examples(
        metadata=metadata, adapter=adapter, k=3
    )
    assert examples == []
    codes = {d["code"] for d in diagnostics}
    assert "predicate_negation_unavailable" in codes
    assert "no_predicate_examples" in codes


def test_get_predicate_examples_invalid_k(corpus_root: Path) -> None:
    metadata = extract_predicate_metadata(rule_id="py.nullderef")
    adapter = LocalFixtureCorpusAdapter(corpus_root)
    with pytest.raises(ValueError):
        get_predicate_examples(metadata=metadata, adapter=adapter, k=0)
