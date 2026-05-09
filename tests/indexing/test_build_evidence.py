"""Tests for the build/test evidence detector."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.indexing.build_evidence import BuildTestEvidenceDetector
from llm_sca_tooling.indexing.scanner import ScannedFile
from llm_sca_tooling.schemas.enums import GraphNodeType, IndexStatus
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef

TS = "2026-05-09T00:00:00Z"


@pytest.fixture
def repo() -> RepoRef:
    return RepoRef(repo_id="repo:bte-test", name="bte-test")


@pytest.fixture
def snapshot(repo: RepoRef) -> SnapshotRef:
    return SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="cafebabe" * 5,
        branch="main",
        worktree_snapshot_id=None,
        dirty=False,
        index_status=IndexStatus.FRESH,
        captured_ts=TS,
    )


def _scanned(
    tmp_path: Path, rel_path: str, content: str = "", is_test: bool = False
) -> ScannedFile:
    abs_path = tmp_path / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(content, encoding="utf-8")
    return ScannedFile(
        path=rel_path,
        abs_path=abs_path,
        language="python",
        size_bytes=len(content.encode()),
        sha256="0" * 64,
        is_test=is_test,
        is_generated=False,
    )


def test_detect_pyproject_produces_build_target(
    tmp_path: Path, repo: RepoRef, snapshot: SnapshotRef
) -> None:
    content = "[tool.pytest.ini_options]\ntestpaths=['tests']\n"
    files = [_scanned(tmp_path, "pyproject.toml", content)]
    detector = BuildTestEvidenceDetector()
    result = detector.detect(tmp_path, repo, snapshot, files)
    build_nodes = [n for n in result.nodes if n.node_type == GraphNodeType.BUILD_TARGET]
    assert build_nodes, "Expected BUILD_TARGET node for pyproject.toml"
    assert any("pyproject.toml" in n.label for n in build_nodes)


def test_detect_tox_ini_produces_build_target(
    tmp_path: Path, repo: RepoRef, snapshot: SnapshotRef
) -> None:
    content = "[tox]\nenvlist = py312\n"
    files = [_scanned(tmp_path, "tox.ini", content)]
    detector = BuildTestEvidenceDetector()
    result = detector.detect(tmp_path, repo, snapshot, files)
    build_nodes = [n for n in result.nodes if n.node_type == GraphNodeType.BUILD_TARGET]
    assert any("tox.ini" in n.label for n in build_nodes)


def test_detect_empty_file_list_returns_empty_result(
    tmp_path: Path, repo: RepoRef, snapshot: SnapshotRef
) -> None:
    detector = BuildTestEvidenceDetector()
    result = detector.detect(tmp_path, repo, snapshot, files=[])
    assert result.nodes == []


def test_detect_test_file_produces_test_node(
    tmp_path: Path, repo: RepoRef, snapshot: SnapshotRef
) -> None:
    files = [
        _scanned(tmp_path, "tests/test_core.py", "def test_foo(): pass", is_test=True)
    ]
    detector = BuildTestEvidenceDetector()
    result = detector.detect(tmp_path, repo, snapshot, files)
    test_nodes = [n for n in result.nodes if n.node_type == GraphNodeType.TEST]
    assert test_nodes, "Expected TEST node for test file"


def test_detect_ci_workflow_produces_ci_job(
    tmp_path: Path, repo: RepoRef, snapshot: SnapshotRef
) -> None:
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    detector = BuildTestEvidenceDetector()
    result = detector.detect(tmp_path, repo, snapshot, files=[])
    ci_nodes = [n for n in result.nodes if n.node_type == GraphNodeType.CI_JOB]
    assert ci_nodes, "Expected CI_JOB node for GitHub Actions workflow"
