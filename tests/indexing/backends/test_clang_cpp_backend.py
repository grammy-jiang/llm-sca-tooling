"""Real libclang C/C++ backend — parser-grade facts + fallback delegation.

Asserts facts the regex parser cannot produce: resolved methods, #include
edges, and cross-file call edges (caller defined in one file, callee in
another) resolved through clang's AST. When libclang is unavailable the
backend delegates to the regex fallback instead of failing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from llm_sca_tooling.indexing.backends.base import BackendResult, IndexingContext
from llm_sca_tooling.indexing.backends.cpp.clang_backend import ClangCppBackend
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.schemas.graph import GraphEdgeType, GraphNodeType
from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    IndexStatus,
    RepoRef,
    SnapshotRef,
)

NOW = datetime.now(UTC).isoformat()

UTIL_H = """\
#pragma once

int helper(int x);

class Calc {
public:
  int compute(int n);
};
"""

UTIL_CPP = """\
#include "util.h"

int helper(int x) {
  return x * 2;
}

int Calc::compute(int n) {
  return helper(n);
}
"""


def _context(repo_root: Path) -> IndexingContext:
    repo = RepoRef(repo_id="repo:cpp", name=repo_root.name)
    snapshot = SnapshotRef(
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
        snapshot_ref=snapshot,
        config=IndexingConfig(),
        run_id="run:cpp",
    )


def _labels(result: BackendResult, node_type: GraphNodeType) -> set[str]:
    return {n.label for n in result.nodes if n.node_type == node_type}


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "cpp_repo"
    repo.mkdir()
    (repo / "util.h").write_text(UTIL_H)
    (repo / "util.cpp").write_text(UTIL_CPP)
    return repo


async def test_emits_parser_grade_symbols_and_methods(tmp_path: Path) -> None:
    if not ClangCppBackend().is_available():
        import pytest

        pytest.skip("libclang not available")
    repo = _make_repo(tmp_path)
    files = sorted(repo.glob("*"))
    result = await ClangCppBackend().index_files(_context(repo), files)

    funcs = _labels(result, GraphNodeType.function)
    assert {"helper", "compute"} <= funcs  # compute is a method — regex misses it
    assert "Calc" in _labels(result, GraphNodeType.class_)

    sym_nodes = [n for n in result.nodes if n.label in {"helper", "compute"}]
    assert sym_nodes
    assert all(n.provenance.derivation == DerivationType.parser for n in sym_nodes)
    assert all(n.provenance.confidence >= 0.9 for n in sym_nodes)


async def test_resolves_cross_file_call_and_include_edges(tmp_path: Path) -> None:
    if not ClangCppBackend().is_available():
        import pytest

        pytest.skip("libclang not available")
    repo = _make_repo(tmp_path)
    files = sorted(repo.glob("*"))
    result = await ClangCppBackend().index_files(_context(repo), files)
    by_id = {n.node_id: n for n in result.nodes}

    # #include "util.h" -> import edge util.cpp -> util.h
    imports = {
        (by_id[e.source_id].file_path, by_id[e.target_id].file_path)
        for e in result.edges
        if e.edge_type == GraphEdgeType.imports
        and e.source_id in by_id
        and e.target_id in by_id
    }
    assert ("util.cpp", "util.h") in imports

    # Calc::compute calls helper (both definitions in util.cpp) — AST resolved.
    calls = {
        (by_id[e.source_id].qualified_name, by_id[e.target_id].qualified_name)
        for e in result.edges
        if e.edge_type == GraphEdgeType.calls
        and e.source_id in by_id
        and e.target_id in by_id
    }
    assert ("Calc::compute", "helper") in calls


async def test_reports_real_libclang_version(tmp_path: Path) -> None:
    if not ClangCppBackend().is_available():
        import pytest

        pytest.skip("libclang not available")
    repo = _make_repo(tmp_path)
    backend = ClangCppBackend()
    await backend.index_files(_context(repo), sorted(repo.glob("*")))
    assert backend.backend_version() == "libclang"


async def test_delegates_to_fallback_when_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(ClangCppBackend, "is_available", lambda self: False)
    repo = _make_repo(tmp_path)
    result = await ClangCppBackend().index_files(_context(repo), sorted(repo.glob("*")))
    assert result.backend_id == "cpp.heuristic"
    assert "helper" in _labels(result, GraphNodeType.function)


async def test_parse_failure_falls_back(tmp_path: Path, monkeypatch) -> None:
    def boom(self, context, files):
        raise RuntimeError("clang exploded")

    monkeypatch.setattr(ClangCppBackend, "is_available", lambda self: True)
    monkeypatch.setattr(ClangCppBackend, "_index_with_clang", boom)
    repo = _make_repo(tmp_path)
    result = await ClangCppBackend().index_files(_context(repo), sorted(repo.glob("*")))
    assert result.backend_id == "cpp.heuristic"
    assert any(d.code == "clang_backend_failed" for d in result.diagnostics)
