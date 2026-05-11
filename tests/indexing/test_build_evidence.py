"""Tests for the build/test evidence detector."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.build_evidence import BuildEvidenceDetector
from llm_sca_tooling.schemas.graph import GraphNodeType
from llm_sca_tooling.schemas.provenance import IndexStatus, RepoRef, SnapshotRef

NOW = "2026-05-09T12:00:00Z"


def _refs(repo_id: str) -> tuple[RepoRef, SnapshotRef]:
    return (
        RepoRef(repo_id=repo_id, name="test"),
        SnapshotRef(
            repo_id=repo_id,
            git_sha="abc",
            branch="main",
            dirty=False,
            index_status=IndexStatus.fresh,
            captured_ts=NOW,
        ),
    )


def test_detects_pyproject_toml(python_basic_repo: Path) -> None:
    detector = BuildEvidenceDetector()
    repo, snap = _refs("repo:test")
    ev = detector.detect(python_basic_repo, repo, snap)
    assert ev.has_pytest is True
    assert any("pyproject.toml" in f for f in ev.package_metadata_files)


def test_detects_tests_directory(python_basic_repo: Path) -> None:
    detector = BuildEvidenceDetector()
    repo, snap = _refs("repo:test")
    ev = detector.detect(python_basic_repo, repo, snap)
    assert ev.has_tests_dir is True


def test_emits_build_target_nodes(python_basic_repo: Path) -> None:
    detector = BuildEvidenceDetector()
    repo, snap = _refs("repo:test")
    ev = detector.detect(python_basic_repo, repo, snap)
    build_nodes = [n for n in ev.nodes if n.node_type == GraphNodeType.build_target]
    assert len(build_nodes) > 0


def test_no_ci_files_in_basic_fixture(python_basic_repo: Path) -> None:
    detector = BuildEvidenceDetector()
    repo, snap = _refs("repo:test")
    ev = detector.detect(python_basic_repo, repo, snap)
    assert ev.has_ci is False


def test_detects_github_ci(tmp_path: Path) -> None:
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text(
        "name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
    )
    detector = BuildEvidenceDetector()
    repo, snap = _refs("repo:test")
    ev = detector.detect(tmp_path, repo, snap)
    assert ev.has_ci is True
    ci_nodes = [n for n in ev.nodes if n.node_type == GraphNodeType.ci_job]
    assert len(ci_nodes) > 0
