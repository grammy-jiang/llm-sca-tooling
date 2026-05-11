"""Tests for the Python AST backend."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.backends.base import IndexingContext
from llm_sca_tooling.indexing.backends.python_ast import (
    ImportResolution,
    PythonASTBackend,
    classify_import,
)
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.schemas.graph import GraphEdgeType, GraphNodeType
from llm_sca_tooling.schemas.provenance import (
    IndexStatus,
    RepoRef,
    SnapshotRef,
)

NOW = "2026-05-09T12:00:00Z"


def _make_context(repo_root: Path) -> IndexingContext:
    repo_id = "repo:test"
    repo_ref = RepoRef(repo_id=repo_id, name="test")
    snap_ref = SnapshotRef(
        repo_id=repo_id,
        git_sha="abc",
        branch="main",
        dirty=False,
        index_status=IndexStatus.fresh,
        captured_ts=NOW,
    )
    return IndexingContext(
        repo_root=repo_root,
        repo_ref=repo_ref,
        snapshot_ref=snap_ref,
        config=IndexingConfig(),
        run_id="run:test",
    )


async def test_python_ast_backend_finds_functions(python_basic_repo: Path) -> None:
    ctx = _make_context(python_basic_repo)
    py_files = list(python_basic_repo.rglob("*.py"))
    backend = PythonASTBackend()
    result = await backend.index_files(ctx, py_files)
    functions = [n for n in result.nodes if n.node_type == GraphNodeType.function]
    assert len(functions) > 0


async def test_python_ast_backend_finds_classes(python_basic_repo: Path) -> None:
    ctx = _make_context(python_basic_repo)
    py_files = list(python_basic_repo.rglob("*.py"))
    backend = PythonASTBackend()
    result = await backend.index_files(ctx, py_files)
    classes = [n for n in result.nodes if n.node_type == GraphNodeType.class_]
    assert len(classes) > 0, "Expected at least one class node"


async def test_python_ast_backend_finds_test_nodes(python_basic_repo: Path) -> None:
    ctx = _make_context(python_basic_repo)
    py_files = list(python_basic_repo.rglob("*.py"))
    backend = PythonASTBackend()
    result = await backend.index_files(ctx, py_files)
    tests = [n for n in result.nodes if n.node_type == GraphNodeType.test]
    assert len(tests) > 0, "Expected test nodes from test_core.py"


async def test_python_ast_backend_syntax_error_produces_diagnostic(
    tmp_path: Path,
) -> None:
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def foo(\n  # unclosed")
    ctx = _make_context(tmp_path)
    backend = PythonASTBackend()
    result = await backend.index_files(ctx, [bad_file])
    assert result.files_skipped >= 1
    assert any("SYNTAX_ERROR" in d.code for d in result.diagnostics)


async def test_python_ast_backend_contains_edges_emitted(
    python_basic_repo: Path,
) -> None:
    ctx = _make_context(python_basic_repo)
    py_files = list(python_basic_repo.rglob("*.py"))
    backend = PythonASTBackend()
    result = await backend.index_files(ctx, py_files)
    contains = [e for e in result.edges if e.edge_type == GraphEdgeType.contains]
    assert len(contains) > 0


async def test_python_ast_backend_emits_same_module_call_edges(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text(
        "def helper():\n    return 1\n\n"
        "def caller():\n    return helper()\n\n"
        "class Service:\n    def run(self):\n        return helper()\n"
    )
    ctx = _make_context(tmp_path)
    result = await PythonASTBackend().index_files(ctx, [source])
    calls = [edge for edge in result.edges if edge.edge_type == GraphEdgeType.calls]
    assert calls


async def test_python_ast_backend_detect_capabilities(tmp_path: Path) -> None:
    caps = await PythonASTBackend().detect_capabilities(_make_context(tmp_path), [])
    assert caps.installed is True
    assert "function" in caps.supported_node_types


async def test_python_ast_backend_skips_non_python_files(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("# docs")
    result = await PythonASTBackend().index_files(_make_context(tmp_path), [source])
    assert result.files_processed == 0
    assert result.files_skipped == 0


def test_classify_import_external(tmp_path: Path) -> None:
    c = classify_import("os", [], False, 0, "pkg.core", tmp_path, "src/pkg/core.py")
    assert c.resolution == ImportResolution.external_dependency


def test_classify_import_empty_module_is_unresolved(tmp_path: Path) -> None:
    c = classify_import(None, [], False, 0, "pkg.core", tmp_path, "pkg/core.py")
    assert c.resolution == ImportResolution.unresolved


def test_classify_import_relative_package(python_basic_repo: Path) -> None:
    c = classify_import(
        "helpers",
        [],
        True,
        1,
        "pkg.core",
        python_basic_repo / "src",
        "pkg/core.py",
    )
    assert c.resolution == ImportResolution.resolved_internal


def test_classify_import_internal_relative(python_basic_repo: Path) -> None:
    c = classify_import(
        "helpers",
        [],
        True,
        1,
        "pkg.core",
        python_basic_repo / "src",
        "pkg/core.py",
    )
    # Should resolve to helpers.py if it exists
    # Since we're looking from src/pkg/core.py going up 1 level (pkg) then helpers
    assert c.resolution in (
        ImportResolution.resolved_internal,
        ImportResolution.unresolved,
    )


def test_classify_import_unknown_is_external(tmp_path: Path) -> None:
    c = classify_import(
        "completely_unknown_pkg", [], False, 0, "main", tmp_path, "main.py"
    )
    assert c.resolution == ImportResolution.external_dependency
