"""Cache invalidation hardening."""

from __future__ import annotations

import uuid

from llm_sca_tooling.hardening.models import CacheInvalidationEvent


class CacheInvalidationHardener:
    def __init__(self) -> None:
        self._cache_keys: dict[str, tuple[str, str, str]] = {}
        self.events: list[CacheInvalidationEvent] = []

    def register_cache_key(
        self, key: str, *, repo_id: str, git_sha: str, file_path: str
    ) -> None:
        self._cache_keys[key] = (repo_id, git_sha, file_path)

    def invalidate_for_graph_update(
        self, *, repo_id: str, git_sha: str, changed_files: list[str]
    ) -> CacheInvalidationEvent:
        changed = set(changed_files)
        invalidated = [
            key
            for key, (key_repo, key_sha, file_path) in self._cache_keys.items()
            if key_repo == repo_id and (key_sha != git_sha or file_path in changed)
        ]
        for key in invalidated:
            self._cache_keys.pop(key, None)
        event = CacheInvalidationEvent(
            event_id=f"cache-invalidate:{uuid.uuid4().hex}",
            repo_id=repo_id,
            git_sha=git_sha,
            changed_files=changed_files,
            invalidated_keys=invalidated,
        )
        self.events.append(event)
        return event

    def verify_cache_consistency(
        self, *, repo_id: str, git_sha: str
    ) -> dict[str, object]:
        stale = [
            key
            for key, (key_repo, key_sha, _file_path) in self._cache_keys.items()
            if key_repo == repo_id and key_sha != git_sha
        ]
        return {
            "repo_id": repo_id,
            "git_sha": git_sha,
            "consistent": not stale,
            "stale_keys": stale,
            "diagnostics": [{"code": "stale_cache", "key": key} for key in stale],
        }
