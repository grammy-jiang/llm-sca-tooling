from __future__ import annotations

from llm_sca_tooling.indexing.backends.python_ast import PythonAstBackend
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.git_metadata import capture_snapshot
from llm_sca_tooling.indexing.scanner import FileScanner
from llm_sca_tooling.schemas.enums import GraphEdgeType, GraphNodeType
from llm_sca_tooling.schemas.provenance import RepoRef


def test_python_ast_emits_symbols_imports_tests_and_calls(python_basic_repo) -> None:
    config = IndexingConfig()
    repo = RepoRef(repo_id="repo:test", name="test")
    snapshot, _, _ = capture_snapshot(repo.repo_id, python_basic_repo, config)
    scan = FileScanner(config).scan(python_basic_repo, repo, snapshot)
    result = PythonAstBackend().index_files(python_basic_repo, repo, snapshot, scan.files)
    node_types = {node.node_type for node in result.nodes}
    edge_types = {edge.edge_type for edge in result.edges}
    assert GraphNodeType.CLASS in node_types
    assert GraphNodeType.FUNCTION in node_types
    assert GraphNodeType.TEST in node_types
    assert GraphEdgeType.IMPORTS in edge_types
    assert GraphEdgeType.CALLS in edge_types
    assert GraphEdgeType.TESTS in edge_types


def test_python_ast_syntax_error_is_diagnostic(python_basic_repo) -> None:
    (python_basic_repo / "src" / "pkg" / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    config = IndexingConfig()
    repo = RepoRef(repo_id="repo:test", name="test")
    snapshot, _, _ = capture_snapshot(repo.repo_id, python_basic_repo, config)
    scan = FileScanner(config).scan(python_basic_repo, repo, snapshot)
    result = PythonAstBackend().index_files(python_basic_repo, repo, snapshot, scan.files)
    assert any(diagnostic.code == "python_parse_failed" for diagnostic in result.diagnostics)
