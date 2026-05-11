"""Tests for the symbol summary cache."""

from __future__ import annotations

from llm_sca_tooling.indexing.summaries import SummaryCache


def test_cache_miss_returns_none() -> None:
    cache = SummaryCache()
    result = cache.get("repo:1", "node:1", "snap:1", "hash:1")
    assert result is None


def test_cache_hit_after_put() -> None:
    cache = SummaryCache()
    record = cache.put(
        "repo:1",
        "node:1",
        "pkg.core.Greeter",
        "src/pkg/core.py",
        "snap:1",
        "hash:abc",
        "A greeter class.",
    )
    assert record.summary_text == "A greeter class."
    hit = cache.get("repo:1", "node:1", "snap:1", "hash:abc")
    assert hit is not None
    assert hit.summary_text == "A greeter class."


def test_cache_miss_after_file_hash_changes() -> None:
    cache = SummaryCache()
    cache.put("repo:1", "node:1", "sym", "file.py", "snap:1", "hash:old", "old summary")
    hit = cache.get("repo:1", "node:1", "snap:1", "hash:new")
    assert hit is None


def test_cache_key_includes_snapshot_identity() -> None:
    cache = SummaryCache()
    cache.put("repo:1", "node:1", "sym", "file.py", "snap:A", "hash:x", "summary A")
    # Different snapshot → miss
    hit = cache.get("repo:1", "node:1", "snap:B", "hash:x")
    assert hit is None


def test_invalidate_for_file() -> None:
    cache = SummaryCache()
    cache.put("repo:1", "node:1", "sym", "file.py", "snap:1", "hash:abc", "summary 1")
    cache.put("repo:1", "node:2", "sym2", "other.py", "snap:1", "hash:def", "summary 2")
    count = cache.invalidate_for_file("repo:1", "file.py")
    assert count == 1
    assert cache.get("repo:1", "node:1", "snap:1", "hash:abc") is None
    assert cache.get("repo:1", "node:2", "snap:1", "hash:def") is not None


def test_invalidated_record_not_returned() -> None:
    cache = SummaryCache()
    cache.put("repo:1", "node:1", "sym", "file.py", "snap:1", "hash:abc", "summary")
    cache.invalidate_for_file("repo:1", "file.py")
    hit = cache.get("repo:1", "node:1", "snap:1", "hash:abc")
    assert hit is None
