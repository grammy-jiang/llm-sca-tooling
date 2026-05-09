"""Tests for the git blame collector."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llm_sca_tooling.indexing.blame import BlameCollector
from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.schemas.enums import IndexStatus
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef

TS = "2026-05-09T00:00:00Z"

_GIT_BLAME_OUTPUT = """\
abc1234567890000000000000000000000000001 1 1 1
author Alice
author-time 1700000000
summary Initial commit
filename src/main.py
\tdef foo():
abc1234567890000000000000000000000000002 2 2 1
author Bob
author-time 1700001000
summary Add bar
filename src/main.py
\t    pass
"""


@pytest.fixture
def repo() -> RepoRef:
    return RepoRef(repo_id="repo:blame-test", name="blame-test")


@pytest.fixture
def snapshot(repo: RepoRef) -> SnapshotRef:
    return SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="abc123ef" * 5,
        branch="main",
        worktree_snapshot_id=None,
        dirty=False,
        index_status=IndexStatus.FRESH,
        captured_ts=TS,
    )


def _provenance(repo, snapshot):
    return make_provenance(source_tool="test", repo=repo, snapshot=snapshot)


def test_blame_collector_init() -> None:
    collector = BlameCollector()
    assert hasattr(collector, "collect")


def test_collect_returns_blame_unavailable_for_dirty_snapshot(
    tmp_path: Path, repo: RepoRef, snapshot: SnapshotRef
) -> None:
    dirty = SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="abc",
        branch="main",
        worktree_snapshot_id="dirty:1",
        dirty=True,
        index_status=IndexStatus.PARTIAL,
        captured_ts=TS,
    )
    collector = BlameCollector()
    prov = _provenance(repo, dirty)
    chain = collector.collect(
        tmp_path, repo, "snap:dirty", dirty, "src/main.py", prov, tmp_path / "artifacts"
    )
    assert any(d.code == "blame_unavailable" for d in chain.diagnostics)


def test_collect_returns_diagnostic_for_non_git_repo(
    tmp_path: Path, repo: RepoRef, snapshot: SnapshotRef
) -> None:
    collector = BlameCollector()
    prov = _provenance(repo, snapshot)
    chain = collector.collect(
        tmp_path,
        repo,
        "snap:abc",
        snapshot,
        "src/main.py",
        prov,
        tmp_path / "artifacts",
    )
    # No .git directory → blame_unavailable diagnostic
    assert any(d.code == "blame_unavailable" for d in chain.diagnostics)


def test_collect_parses_git_blame_output(
    tmp_path: Path, repo: RepoRef, snapshot: SnapshotRef
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()

    mock_result = MagicMock()
    mock_result.stdout = _GIT_BLAME_OUTPUT

    collector = BlameCollector()
    prov = _provenance(repo, snapshot)

    with patch("subprocess.run", return_value=mock_result):
        chain = collector.collect(
            repo_root,
            repo,
            "snap:abc",
            snapshot,
            "src/main.py",
            prov,
            tmp_path / "artifacts",
        )

    assert len(chain.line_entries) > 0
    assert chain.line_entries[0].commit_sha.startswith("abc123")


def test_collect_handles_empty_blame_output(
    tmp_path: Path, repo: RepoRef, snapshot: SnapshotRef
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()

    mock_result = MagicMock()
    mock_result.stdout = ""

    collector = BlameCollector()
    prov = _provenance(repo, snapshot)

    with patch("subprocess.run", return_value=mock_result):
        chain = collector.collect(
            repo_root,
            repo,
            "snap:abc",
            snapshot,
            "src/main.py",
            prov,
            tmp_path / "artifacts",
        )

    assert chain.line_entries == []
    assert chain.artifact_ref is not None
