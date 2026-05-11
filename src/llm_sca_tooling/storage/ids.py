"""ID generation utilities for storage entities."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

__all__ = [
    "new_uuid",
    "generate_repo_id",
    "generate_snapshot_id",
    "hash_path",
    "hash_url",
]

_PREFIX_RUN = "run"
_PREFIX_REPO = "repo"
_PREFIX_SNAP = "snap"
_PREFIX_ARTIFACT = "art"
_PREFIX_INCIDENT = "inc"
_PREFIX_PROMOTION = "promo"


def new_uuid(prefix: str = "") -> str:
    """Return a new UUID4-based ID with an optional prefix."""
    uid = uuid.uuid4().hex
    return f"{prefix}:{uid}" if prefix else uid


def hash_path(path: Path) -> str:
    """Return a stable SHA-256 hex digest of a canonical path string."""
    canonical = str(path.resolve())
    return hashlib.sha256(canonical.encode()).hexdigest()[:32]


def hash_url(url: str) -> str:
    """Return a stable SHA-256 hex digest of a remote URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:32]


def generate_repo_id(path: Path, remote_url: str | None = None) -> str:
    """Generate a stable repo ID from the canonical path and optional remote URL.

    The ID is deterministic: the same path + remote URL always produces the
    same ID.  It never exposes the raw path in the ID itself.
    """
    canonical = str(path.resolve())
    raw = canonical + "|" + (remote_url or "")
    digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
    return f"{_PREFIX_REPO}:{digest}"


def generate_snapshot_id(
    repo_id: str, git_sha: str | None, worktree_id: str | None = None
) -> str:
    """Generate a stable snapshot ID from repo ID and git SHA (or worktree ID)."""
    key = worktree_id or git_sha or new_uuid()
    digest = hashlib.sha256(f"{repo_id}|{key}".encode()).hexdigest()[:24]
    return f"{_PREFIX_SNAP}:{digest}"
