from __future__ import annotations

from llm_sca_tooling.indexing.build_evidence import BuildTestEvidenceDetector
from llm_sca_tooling.indexing.blame import BlameCollector
from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.git_metadata import capture_snapshot
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.indexing.scanner import FileScanner
from llm_sca_tooling.indexing.summaries import SummaryCache, SymbolSummaryRecord
from llm_sca_tooling.schemas.enums import DerivationType, GraphNodeType
from llm_sca_tooling.schemas.provenance import RepoRef


def test_build_test_evidence_detects_pytest_ci_and_tests(python_basic_repo) -> None:
    config = IndexingConfig()
    repo = RepoRef(repo_id="repo:test", name="test")
    snapshot, _, _ = capture_snapshot(repo.repo_id, python_basic_repo, config)
    scan = FileScanner(config).scan(python_basic_repo, repo, snapshot)
    result = BuildTestEvidenceDetector().detect(python_basic_repo, repo, snapshot, scan.files)
    node_types = {node.node_type for node in result.nodes}
    assert GraphNodeType.BUILD_TARGET in node_types
    assert GraphNodeType.TEST in node_types
    assert GraphNodeType.CI_JOB in node_types
    assert all(not node.properties.get("tests_run", True) for node in result.nodes)


def test_blame_chain_artifact_and_summary_invalidation(python_basic_repo, tmp_path) -> None:
    config = IndexingConfig()
    repo = RepoRef(repo_id="repo:test", name="test")
    snapshot, snapshot_id, _ = capture_snapshot(repo.repo_id, python_basic_repo, config)
    provenance = make_provenance(source_tool="test", repo=repo, snapshot=snapshot)
    chain = BlameCollector().collect(python_basic_repo, repo, snapshot_id, snapshot, "src/pkg/core.py", provenance, tmp_path / "artifacts")
    assert chain.artifact_ref is not None
    cache = SummaryCache(tmp_path / "summaries")
    summary_id = cache.key(repo_id=repo.repo_id, snapshot_id=snapshot_id, symbol_node_id="node:1", file_path="src/pkg/core.py", file_hash="hash")
    cache.put(
        SymbolSummaryRecord(
            summary_id=summary_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot_id,
            symbol_node_id="node:1",
            symbol_path="pkg.core:parse_config",
            file_path="src/pkg/core.py",
            file_hash="hash",
            summary_text="stub",
            confidence=0.2,
            derivation=DerivationType.HEURISTIC,
            generator_id="stub",
            created_ts="2026-05-09T00:00:00Z",
            provenance=provenance,
        )
    )
    assert cache.get_current(summary_id) is not None
    assert cache.invalidate_for_files(["src/pkg/core.py"], "changed") == 1
    assert cache.get_current(summary_id) is None
