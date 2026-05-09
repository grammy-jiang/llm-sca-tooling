from __future__ import annotations

from llm_sca_tooling.indexing.backends.ctags import CtagsBackend, parse_ctags_json_lines
from llm_sca_tooling.indexing.backends.tree_sitter import TreeSitterBackend
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.git_metadata import capture_snapshot
from llm_sca_tooling.indexing.scanner import FileScanner
from llm_sca_tooling.schemas.enums import GraphNodeType
from llm_sca_tooling.schemas.provenance import RepoRef


def test_optional_backends_report_capabilities() -> None:
    assert CtagsBackend().detect_capabilities().backend_id == "ctags"
    assert TreeSitterBackend().detect_capabilities().backend_id == "tree-sitter"


def test_ctags_json_fixture_parses(python_basic_repo) -> None:
    config = IndexingConfig()
    repo = RepoRef(repo_id="repo:test", name="test")
    snapshot, _, _ = capture_snapshot(repo.repo_id, python_basic_repo, config)
    module = FileScanner(config).scan(python_basic_repo, repo, snapshot).nodes[0]
    result = parse_ctags_json_lines(['{"name":"thing","kind":"function","line":1}'], repo, snapshot, module, "src/pkg/core.py")
    assert result.nodes[0].node_type == GraphNodeType.FUNCTION
