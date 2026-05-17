"""Regression tests for the Markdown indexer backend.

Closes May-2026 audit Finding 4: Markdown evidence used to ship with
``span=null``.  These tests pin the contract that ``.md`` files produce
``document`` heading nodes with file:line spans so audit clauses can be
cited deterministically.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from llm_sca_tooling.indexing.backends.base import IndexingContext
from llm_sca_tooling.indexing.backends.markdown import MarkdownBackend
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.schemas.graph import GraphNodeType
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef


def _make_refs(repo_id: str) -> tuple[RepoRef, SnapshotRef]:
    repo = RepoRef(repo_id=repo_id)
    snap = SnapshotRef(repo_id=repo_id, captured_ts="2026-05-18T00:00:00+00:00")
    return repo, snap


def _context(tmp_path: Path) -> IndexingContext:
    repo_ref, snap_ref = _make_refs("repo:test-md")
    return IndexingContext(
        repo_root=tmp_path,
        repo_ref=repo_ref,
        snapshot_ref=snap_ref,
        config=IndexingConfig(),
        run_id="run:test-md",
    )


def test_markdown_backend_emits_heading_nodes_with_spans(tmp_path: Path) -> None:
    md = tmp_path / "README.md"
    md.write_text(
        "# Project\n"
        "\n"
        "Intro paragraph.\n"
        "\n"
        "## Setup\n"
        "\n"
        "Install steps.\n"
        "\n"
        "## Usage\n"
        "\n"
        "Examples.\n"
        "\n"
        "### Advanced\n"
        "Deep dive.\n"
    )
    backend = MarkdownBackend()
    result = asyncio.run(backend.index_files(_context(tmp_path), [md]))
    assert result.files_processed == 1
    headings = [n for n in result.nodes if n.node_type == GraphNodeType.document]
    levels = [n.properties["level"] for n in headings]
    labels = [n.label for n in headings]
    assert levels == [1, 2, 2, 3]
    assert labels == ["Project", "Setup", "Usage", "Advanced"]
    # Each heading carries a SourceSpan with file:line evidence.
    for node in headings:
        assert node.span is not None
        assert node.span.file_path == "README.md"
        assert node.span.start_line >= 1


def test_markdown_backend_skips_headings_inside_fenced_code(tmp_path: Path) -> None:
    """``markdown-it-py`` correctly classifies fenced code as not a heading.

    Regression: a regex-only parser would mistake the ``# fake`` line inside
    the code fence for a level-1 heading.  We verify the real heading count
    is 2 (``Real`` + ``Also real``) instead of 3.
    """
    md = tmp_path / "fence.md"
    md.write_text(
        "# Real\n"
        "\n"
        "```python\n"
        "# fake heading inside code\n"
        "x = 1\n"
        "```\n"
        "\n"
        "## Also real\n"
        "Body.\n"
    )
    backend = MarkdownBackend()
    result = asyncio.run(backend.index_files(_context(tmp_path), [md]))
    headings = [n for n in result.nodes if n.node_type == GraphNodeType.document]
    labels = [n.label for n in headings]
    assert labels == ["Real", "Also real"]


def test_markdown_backend_qualified_name_breadcrumb(tmp_path: Path) -> None:
    md = tmp_path / "guide.md"
    md.write_text("# Top\n## Mid\n### Leaf\n## Sibling\n")
    backend = MarkdownBackend()
    result = asyncio.run(backend.index_files(_context(tmp_path), [md]))
    qualified = [
        n.qualified_name for n in result.nodes if n.node_type == GraphNodeType.document
    ]
    assert qualified[0] == "guide.md#Top"
    assert qualified[1] == "guide.md#Top > Mid"
    assert qualified[2] == "guide.md#Top > Mid > Leaf"
    # Sibling resets the level-3 child.
    assert qualified[3] == "guide.md#Top > Sibling"


def test_markdown_backend_handles_empty_and_no_headings(tmp_path: Path) -> None:
    empty = tmp_path / "empty.md"
    empty.write_text("")
    no_headings = tmp_path / "plain.md"
    no_headings.write_text("Just a paragraph, no headings here.\n")
    backend = MarkdownBackend()
    result = asyncio.run(backend.index_files(_context(tmp_path), [empty, no_headings]))
    assert result.files_processed == 2
    assert result.nodes == []


@pytest.mark.asyncio
async def test_markdown_backend_capabilities_report() -> None:
    backend = MarkdownBackend()
    caps = await backend.detect_capabilities(
        IndexingContext(
            repo_root=Path(),
            repo_ref=RepoRef(repo_id="r"),
            snapshot_ref=SnapshotRef(
                repo_id="r", captured_ts="2026-05-18T00:00:00+00:00"
            ),
            config=IndexingConfig(),
            run_id="run:caps",
        ),
        [],
    )
    assert caps.backend_id == "markdown"
    assert caps.installed is True
    assert "markdown" in caps.supported_languages
