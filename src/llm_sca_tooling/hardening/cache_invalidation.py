"""Cache invalidation hardening.

Every cached entry carries a ``(repo_id, git_sha)`` composite key.  A cache
hit is only valid when the current graph's ``git_sha`` matches the key.  On
``graph_update`` completion this module invalidates all affected entries and
records events in the operational ledger.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["CacheEntry", "CacheInvalidationHardener"]

logger = get_logger(__name__)

_SECRET_RE = re.compile(
    r"(?i)(password|secret|token|api.?key|private.?key)\s*[:=]\s*\S+"
)


@dataclass
class CacheEntry:
    repo_id: str
    git_sha: str
    key: str
    value: Any
    stale: bool = False


@dataclass
class InvalidationEvent:
    event_id: str
    repo_id: str
    git_sha: str
    affected_keys: list[str]
    ts: str


class CacheInvalidationHardener:
    """Manages cache consistency across ``graph_update`` transitions.

    A cache entry is considered *valid* only when its ``git_sha`` matches
    the current graph SHA for that repo.  On ``graph_update`` the hardener
    invalidates all stale entries for changed file paths and records an
    invalidation event.

    Args:
        ledger: Optional callable to persist ``InvalidationEvent`` dicts.
    """

    def __init__(
        self,
        ledger: Any | None = None,
    ) -> None:
        self._cache: dict[str, CacheEntry] = {}
        self._ledger = ledger

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def put(self, repo_id: str, git_sha: str, key: str, value: Any) -> None:
        """Store *value* under a composite ``(repo_id, git_sha, key)`` cache key."""
        composite = self._composite(repo_id, git_sha, key)
        self._cache[composite] = CacheEntry(
            repo_id=repo_id, git_sha=git_sha, key=key, value=value
        )
        logger.debug("cache put: %s@%s key=%s", repo_id, git_sha[:8], key)

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def get(self, repo_id: str, current_sha: str, key: str) -> tuple[Any, bool]:
        """Return ``(value, hit)`` for the entry matching *current_sha*.

        If an entry exists for a *different* sha the entry is marked stale and
        ``(None, False)`` is returned with a ``stale_cache`` diagnostic logged.
        """
        for entry in self._cache.values():
            if entry.repo_id == repo_id and entry.key == key:
                if entry.git_sha == current_sha and not entry.stale:
                    return entry.value, True
                logger.warning(
                    "stale_cache: repo=%s key=%s cached_sha=%s current_sha=%s",
                    repo_id,
                    key,
                    entry.git_sha[:8],
                    current_sha[:8],
                )
                return None, False
        return None, False

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    def on_graph_update(
        self,
        repo_id: str,
        new_sha: str,
        changed_paths: list[str],
    ) -> InvalidationEvent:
        """Invalidate all cache entries for *repo_id* with paths in *changed_paths*.

        Records an ``InvalidationEvent`` in the operational ledger.
        """
        affected: list[str] = []
        for _key, entry in list(self._cache.items()):
            if entry.repo_id == repo_id and (
                entry.git_sha != new_sha or any(p in entry.key for p in changed_paths)
            ):
                entry.stale = True
                affected.append(entry.key)
                logger.debug(
                    "invalidated cache entry: %s@%s key=%s",
                    repo_id,
                    new_sha[:8],
                    entry.key,
                )

        import uuid  # noqa: PLC0415

        event = InvalidationEvent(
            event_id=f"inv:{uuid.uuid4().hex[:12]}",
            repo_id=repo_id,
            git_sha=new_sha,
            affected_keys=affected,
            ts=datetime.now(UTC).isoformat(),
        )
        if self._ledger is not None:
            self._ledger(event)
        logger.info(
            "cache invalidation: repo=%s sha=%s affected=%d",
            repo_id,
            new_sha[:8],
            len(affected),
        )
        return event

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def verify_cache_consistency(self, repo_id: str) -> dict[str, Any]:
        """Return a consistency report for all cached entries of *repo_id*."""
        entries = [e for e in self._cache.values() if e.repo_id == repo_id]
        stale = [e.key for e in entries if e.stale]
        return {
            "repo_id": repo_id,
            "total_entries": len(entries),
            "stale_entries": len(stale),
            "stale_keys": stale,
            "consistent": len(stale) == 0,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _composite(repo_id: str, git_sha: str, key: str) -> str:
        return f"{repo_id}:{git_sha}:{key}"
