from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.workflows.impl_check.ingestion import ingest_markdown


def test_ingest_inline_markdown() -> None:
    doc, raw = ingest_markdown("# Title\n\nThe system must work.\n")
    assert doc.doc_id.startswith("doc:")
    assert doc.title == "Title"
    assert doc.source_path == "<inline>"
    assert raw.startswith("# Title")
    assert doc.content_hash
    assert doc.ingested_ts


def test_ingest_extracts_title_from_first_h1() -> None:
    doc, _ = ingest_markdown("# Real Title\n## subhead\n")
    assert doc.title == "Real Title"


def test_ingest_path(tmp_path: Path) -> None:
    p = tmp_path / "spec.md"
    p.write_text("# T\nmust do.\n", encoding="utf-8")
    doc, raw = ingest_markdown(p)
    assert doc.source_path == str(p)
    assert raw == "# T\nmust do.\n"


def test_content_hash_stable() -> None:
    a, _ = ingest_markdown("same\n")
    b, _ = ingest_markdown("same\n")
    assert a.content_hash == b.content_hash


def test_empty_content_still_produces_doc() -> None:
    doc, _ = ingest_markdown("")
    assert doc.doc_id


def test_doc_id_derived_from_hash_when_not_given() -> None:
    doc, _ = ingest_markdown("hello")
    assert doc.doc_id.startswith("doc:")
    doc2, _ = ingest_markdown("hello", doc_id="doc:custom")
    assert doc2.doc_id == "doc:custom"
