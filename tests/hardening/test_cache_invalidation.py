"""Tests for CacheInvalidationHardener."""

from __future__ import annotations

from llm_sca_tooling.hardening.cache_invalidation import CacheInvalidationHardener


def test_cache_hit_correct_sha() -> None:
    h = CacheInvalidationHardener()
    h.put("repo1", "abc123", "symbol_summary:foo.py", {"data": 1})
    value, hit = h.get("repo1", "abc123", "symbol_summary:foo.py")
    assert hit
    assert value == {"data": 1}


def test_cache_miss_wrong_sha() -> None:
    h = CacheInvalidationHardener()
    h.put("repo1", "abc123", "symbol_summary:foo.py", {"data": 1})
    value, hit = h.get("repo1", "deadbeef", "symbol_summary:foo.py")
    assert not hit
    assert value is None


def test_on_graph_update_invalidates_affected_entries() -> None:
    events: list[object] = []
    h = CacheInvalidationHardener(ledger=events.append)
    h.put("repo1", "sha1", "symbol_summary:foo.py", {"x": 1})
    h.put("repo1", "sha1", "symbol_summary:bar.py", {"y": 2})

    event = h.on_graph_update("repo1", "sha2", ["foo.py"])  # noqa: F841

    assert len(events) == 1
    # Entry for foo.py is stale
    _, hit = h.get("repo1", "sha2", "symbol_summary:foo.py")
    assert not hit


def test_verify_cache_consistency_reports_stale() -> None:
    h = CacheInvalidationHardener()
    h.put("repo1", "sha1", "key:a", "val")
    h.on_graph_update("repo1", "sha2", ["a"])

    report = h.verify_cache_consistency("repo1")
    assert report["stale_entries"] >= 1
    assert not report["consistent"]
