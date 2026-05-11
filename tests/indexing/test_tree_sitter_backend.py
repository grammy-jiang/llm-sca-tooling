"""Tests for the optional tree-sitter backend."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing import backends as _unused_backends
from llm_sca_tooling.indexing.backends import tree_sitter as ts_mod
from llm_sca_tooling.indexing.backends.base import IndexingContext
from llm_sca_tooling.indexing.backends.tree_sitter import TreeSitterBackend
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.schemas.graph import GraphNode, GraphNodeType
from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    EvidenceStrength,
    IndexStatus,
    Provenance,
    RepoRef,
    SnapshotRef,
)

NOW = "2026-05-09T12:00:00Z"


def _context(repo_root: Path) -> IndexingContext:
    repo = RepoRef(repo_id="repo:ts", name="ts")
    snap = SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="abc",
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )
    return IndexingContext(
        repo_root=repo_root,
        repo_ref=repo,
        snapshot_ref=snap,
        config=IndexingConfig(),
        run_id="run:ts",
    )


async def test_tree_sitter_unavailable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ts_mod, "_try_import_tree_sitter", lambda: (None, None))
    backend = TreeSitterBackend()
    caps = await backend.detect_capabilities(_context(tmp_path), [])
    result = await backend.index_files(_context(tmp_path), [])
    assert caps.installed is False
    assert result.diagnostics[0].code == "TREE_SITTER_UNAVAILABLE"


async def test_tree_sitter_index_files_success_with_parser_stub(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "app.py"
    source.write_text("def f():\n    return 1\n")
    ctx = _context(tmp_path)

    def fake_import():
        return object(), "test-version"

    def fake_parse_file(self, path, language, context):
        prov = Provenance(
            source_tool="tree_sitter",
            repo=context.repo_ref,
            snapshot=context.snapshot_ref,
            derivation=DerivationType.parser,
            confidence=1.0,
            evidence_strength=EvidenceStrength.hard_static,
            created_ts=NOW,
        )
        return [
            GraphNode(
                node_id="node:ts",
                node_type=GraphNodeType.function,
                label="f",
                repo=context.repo_ref,
                snapshot=context.snapshot_ref,
                provenance=prov,
                created_ts=NOW,
            )
        ], []

    monkeypatch.setattr(ts_mod, "_try_import_tree_sitter", fake_import)
    monkeypatch.setattr(TreeSitterBackend, "_parse_file", fake_parse_file)
    backend = TreeSitterBackend()
    result = await backend.index_files(ctx, [source])
    assert backend.backend_version() == "test-version"
    assert result.files_processed == 1
    assert result.nodes[0].label == "f"
    assert _unused_backends.BackendResult is not None


async def test_tree_sitter_index_files_parse_exception(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "app.py"
    source.write_text("def f():\n    return 1\n")

    monkeypatch.setattr(ts_mod, "_try_import_tree_sitter", lambda: (object(), "v"))

    def fail_parse(self, path, language, context):
        raise RuntimeError("bad parse")

    monkeypatch.setattr(TreeSitterBackend, "_parse_file", fail_parse)
    result = await TreeSitterBackend().index_files(_context(tmp_path), [source])
    assert result.files_skipped == 1
    assert result.diagnostics[0].code == "TREE_SITTER_PARSE_ERROR"
