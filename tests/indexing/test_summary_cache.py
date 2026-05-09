"""Tests for SummaryCache."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_sca_tooling.indexing.provenance import make_provenance
from llm_sca_tooling.indexing.summaries import SummaryCache, SymbolSummaryRecord
from llm_sca_tooling.schemas.enums import DerivationType, IndexStatus
from llm_sca_tooling.schemas.provenance import RepoRef, SnapshotRef
from llm_sca_tooling.storage.workspace import _now_ts

TS = "2026-05-09T00:00:00Z"


@pytest.fixture
def repo() -> RepoRef:
    return RepoRef(repo_id="repo:cache-test", name="cache-test")


@pytest.fixture
def snapshot(repo: RepoRef) -> SnapshotRef:
    return SnapshotRef(
        repo_id=repo.repo_id,
        git_sha="cafef00d" * 5,
        branch="main",
        worktree_snapshot_id=None,
        dirty=False,
        index_status=IndexStatus.FRESH,
        captured_ts=TS,
    )


def _make_record(
    cache: SummaryCache,
    repo: RepoRef,
    snapshot: SnapshotRef,
    *,
    file_hash: str = "hash:v1",
) -> SymbolSummaryRecord:
    prov = make_provenance(source_tool="test", repo=repo, snapshot=snapshot)
    summary_id = cache.key(
        repo_id=repo.repo_id,
        snapshot_id=snapshot.git_sha,
        symbol_node_id="node:test:func_a",
        file_path="src/mod.py",
        file_hash=file_hash,
    )
    return SymbolSummaryRecord(
        summary_id=summary_id,
        repo_id=repo.repo_id,
        snapshot_id=snapshot.git_sha,
        symbol_node_id="node:test:func_a",
        symbol_path="mod.func_a",
        file_path="src/mod.py",
        file_hash=file_hash,
        summary_text="Does something useful.",
        confidence=0.95,
        derivation=DerivationType.PARSER,
        generator_id="stub",
        created_ts=_now_ts(),
        provenance=prov,
    )


def test_summary_cache_stores_and_retrieves(
    tmp_path: Path, repo: RepoRef, snapshot: SnapshotRef
) -> None:
    cache = SummaryCache(tmp_path / "summaries")
    record = _make_record(cache, repo, snapshot)
    cache.put(record)

    retrieved = cache.get_current(record.summary_id)
    assert retrieved is not None
    assert retrieved.summary_text == "Does something useful."


def test_summary_cache_miss_returns_none(tmp_path: Path) -> None:
    cache = SummaryCache(tmp_path / "summaries")
    result = cache.get_current("summary:nonexistent")
    assert result is None


def test_summary_cache_invalidated_returns_none(
    tmp_path: Path, repo: RepoRef, snapshot: SnapshotRef
) -> None:
    cache = SummaryCache(tmp_path / "summaries")
    record = _make_record(cache, repo, snapshot)
    cache.put(record)

    # Write the record with an invalidated_ts to simulate invalidation
    invalidated = record.model_copy(
        update={"invalidated_ts": _now_ts(), "invalidation_reason": "file changed"}
    )
    (tmp_path / "summaries" / f"{record.summary_id.replace(':', '_')}.json").write_text(
        invalidated.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )

    result = cache.get_current(record.summary_id)
    assert result is None


def test_summary_cache_key_is_deterministic(
    tmp_path: Path, repo: RepoRef, snapshot: SnapshotRef
) -> None:
    cache = SummaryCache(tmp_path / "summaries")
    key1 = cache.key(
        repo_id=repo.repo_id,
        snapshot_id=snapshot.git_sha,
        symbol_node_id="node:a",
        file_path="src/a.py",
        file_hash="hash:abc",
    )
    key2 = cache.key(
        repo_id=repo.repo_id,
        snapshot_id=snapshot.git_sha,
        symbol_node_id="node:a",
        file_path="src/a.py",
        file_hash="hash:abc",
    )
    assert key1 == key2


def test_summary_cache_different_hashes_produce_different_keys(
    tmp_path: Path, repo: RepoRef, snapshot: SnapshotRef
) -> None:
    cache = SummaryCache(tmp_path / "summaries")
    kwargs = {
        "repo_id": repo.repo_id,
        "snapshot_id": snapshot.git_sha,
        "symbol_node_id": "node:a",
        "file_path": "src/a.py",
    }
    key1 = cache.key(**kwargs, file_hash="hash:v1")
    key2 = cache.key(**kwargs, file_hash="hash:v2")
    assert key1 != key2
