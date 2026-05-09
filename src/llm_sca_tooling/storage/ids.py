"""Stable storage ID helpers."""

from __future__ import annotations

import hashlib
import re

from llm_sca_tooling.schemas.base import canonical_json
from llm_sca_tooling.schemas.provenance import SnapshotRef


def stable_hash(value: str | bytes, *, length: int = 16) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()[:length]


def payload_hash(payload: object) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip().lower()).strip("-")
    return slug or "repo"


def repo_id_for(root_path: str, *, remote_url: str | None = None, name: str | None = None) -> str:
    basis = "\n".join(part for part in [root_path, remote_url or "", name or ""] if part is not None)
    prefix = slugify(name or root_path.rsplit("/", 1)[-1])
    return f"repo:{prefix}:{stable_hash(basis)}"


def snapshot_id_for(snapshot: SnapshotRef, file_state_hash: str | None = None) -> str:
    if snapshot.git_sha and not snapshot.dirty:
        return f"snap:{stable_hash(snapshot.repo_id, length=8)}:{snapshot.git_sha}"
    basis = "|".join(
        [
            snapshot.repo_id,
            snapshot.git_sha or "",
            snapshot.worktree_snapshot_id or "",
            file_state_hash or "",
            snapshot.captured_ts,
        ]
    )
    return f"snap:{stable_hash(snapshot.repo_id, length=8)}:dirty:{stable_hash(basis)}"
