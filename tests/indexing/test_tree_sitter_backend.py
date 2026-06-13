"""Tests for the multi-language tree-sitter backend.

Tree-sitter is the real-grammar structural tier: it parses Python, TS/JS, and
C/C++ with the language's actual grammar (not regex) and emits symbols whose
qualified names match the dedicated backends, so the reconciler merges and
confirms them. Facts sit at confidence 0.8 — below ts-morph/libclang (1.0),
above the heuristic regex backends (0.6).
"""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.backends import tree_sitter as ts_mod
from llm_sca_tooling.indexing.backends.base import IndexingContext
from llm_sca_tooling.indexing.backends.tree_sitter import TreeSitterBackend
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.schemas.graph import GraphNodeType
from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    IndexStatus,
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


def _labels(nodes, node_type: GraphNodeType) -> set[str]:
    return {n.qualified_name for n in nodes if n.node_type == node_type}


async def test_grammars_available_multi_language() -> None:
    backend = TreeSitterBackend()
    langs = backend.supported_languages()
    # Core grammars ship as dependencies; all should load.
    assert {"python", "typescript", "javascript", "c", "cpp"} <= set(langs)
    assert backend.backend_version() == "tree-sitter"


async def test_python_symbols(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("class A:\n    def m(self):\n        pass\n")
    result = await TreeSitterBackend().index_files(
        _context(tmp_path), [tmp_path / "app.py"]
    )
    assert "A" in _labels(result.nodes, GraphNodeType.class_)
    assert result.files_processed == 1


async def test_typescript_qualified_method_matches_ts_morph(tmp_path: Path) -> None:
    (tmp_path / "u.ts").write_text(
        "export class Calc {\n  compute(n: number) { return n; }\n}\n"
        "export function helper(x: number) { return x; }\n"
        "export interface Greeter { greet(): void; }\n"
    )
    result = await TreeSitterBackend().index_files(
        _context(tmp_path), [tmp_path / "u.ts"]
    )
    funcs = _labels(result.nodes, GraphNodeType.function)
    # Qualified method name uses "." to match ts-morph (reconciler merge).
    assert "Calc.compute" in funcs
    assert "helper" in funcs
    assert "Greeter" in _labels(result.nodes, GraphNodeType.interface)


async def test_cpp_qualified_method_matches_libclang(tmp_path: Path) -> None:
    (tmp_path / "u.cpp").write_text(
        "class Calc { public: int compute(int n); };\n"
        "int helper(int x) { return x * 2; }\n"
        "int Calc::compute(int n) { return helper(n); }\n"
    )
    result = await TreeSitterBackend().index_files(
        _context(tmp_path), [tmp_path / "u.cpp"]
    )
    funcs = _labels(result.nodes, GraphNodeType.function)
    # Out-of-line definition keeps its qualified "Calc::compute" (libclang match).
    assert "Calc::compute" in funcs
    assert "helper" in funcs
    assert "Calc" in _labels(result.nodes, GraphNodeType.class_)


async def test_confidence_below_dedicated_backends(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def f():\n    pass\n")
    result = await TreeSitterBackend().index_files(
        _context(tmp_path), [tmp_path / "app.py"]
    )
    node = next(n for n in result.nodes if n.label == "f")
    assert node.provenance.derivation == DerivationType.parser
    assert 0.6 < node.provenance.confidence < 1.0


async def test_unknown_extension_skipped(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_text("not code")
    result = await TreeSitterBackend().index_files(
        _context(tmp_path), [tmp_path / "data.txt"]
    )
    assert result.nodes == []


async def test_no_grammars_degrades_gracefully(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        ts_mod.TreeSitterBackend, "supported_languages", lambda self: []
    )
    result = await TreeSitterBackend().index_files(_context(tmp_path), [])
    assert result.diagnostics[0].code == "TREE_SITTER_UNAVAILABLE"


async def test_parse_exception_skips_file(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def f(): pass\n")

    def boom(self, path, lang_key, context):
        raise RuntimeError("bad parse")

    monkeypatch.setattr(TreeSitterBackend, "_parse_file", boom)
    result = await TreeSitterBackend().index_files(
        _context(tmp_path), [tmp_path / "app.py"]
    )
    assert result.files_skipped == 1
    assert result.diagnostics[0].code == "TREE_SITTER_PARSE_ERROR"
