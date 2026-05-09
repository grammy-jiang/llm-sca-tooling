from __future__ import annotations

from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.git_metadata import capture_snapshot
from llm_sca_tooling.indexing.scanner import FileScanner
from llm_sca_tooling.schemas.enums import GraphNodeType
from llm_sca_tooling.schemas.provenance import RepoRef


def test_scanner_ignores_caches_and_emits_file_graph(python_basic_repo) -> None:
    (python_basic_repo / "__pycache__").mkdir()
    (python_basic_repo / "__pycache__" / "x.py").write_text("bad", encoding="utf-8")
    config = IndexingConfig()
    repo = RepoRef(repo_id="repo:test", name="test")
    snapshot, _, _ = capture_snapshot(repo.repo_id, python_basic_repo, config)
    result = FileScanner(config).scan(python_basic_repo, repo, snapshot)
    paths = {file.path for file in result.files}
    assert "src/pkg/core.py" in paths
    assert "__pycache__/x.py" not in paths
    assert any(node.node_type == GraphNodeType.FILE for node in result.nodes)
    assert result.edges


def test_scanner_reports_binary_and_oversized(python_basic_repo) -> None:
    (python_basic_repo / "binary.bin").write_bytes(b"a\0b")
    (python_basic_repo / "large.py").write_text("x" * 20, encoding="utf-8")
    config = IndexingConfig(max_file_size_bytes=10)
    repo = RepoRef(repo_id="repo:test", name="test")
    snapshot, _, _ = capture_snapshot(repo.repo_id, python_basic_repo, config)
    result = FileScanner(config).scan(python_basic_repo, repo, snapshot)
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert "file_skipped_binary" in codes
    assert "file_skipped_oversized" in codes
