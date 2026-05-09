"""Git metadata and snapshot capture."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import Field

from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.hashing import hash_file, hash_text
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.enums import IndexStatus
from llm_sca_tooling.schemas.provenance import SnapshotRef
from llm_sca_tooling.storage.ids import snapshot_id_for
from llm_sca_tooling.storage.workspace import _now_ts


class GitMetadata(StrictBaseModel):
    is_git: bool
    git_sha: str | None
    branch: str | None
    dirty: bool
    changed_files: list[str] = Field(default_factory=list)
    staged_files: list[str] = Field(default_factory=list)
    untracked_files: list[str] = Field(default_factory=list)
    worktree_snapshot_id: str | None = None


def _git(repo_root: Path, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _git_lines(repo_root: Path, args: list[str]) -> list[str]:
    output = _git(repo_root, args)
    return [] if not output else [line.strip() for line in output.splitlines() if line.strip()]


def collect_git_metadata(repo_root: Path, repo_id: str, config: IndexingConfig) -> GitMetadata:
    is_git = (repo_root / ".git").exists()
    if not is_git:
        return GitMetadata(is_git=False, git_sha=None, branch=None, dirty=False)
    git_sha = _git(repo_root, ["rev-parse", "HEAD"])
    branch = _git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    branch = None if branch == "HEAD" else branch
    changed = sorted(set(_git_lines(repo_root, ["diff", "--name-only"])))
    staged = sorted(set(_git_lines(repo_root, ["diff", "--cached", "--name-only"])))
    untracked = sorted(set(_git_lines(repo_root, ["ls-files", "--others", "--exclude-standard"])))
    status_lines = _git_lines(repo_root, ["status", "--porcelain=v1"])
    dirty = bool(status_lines)
    worktree_snapshot_id = None
    if dirty:
        digest_parts = [repo_id, git_sha or "", "|".join(changed), "|".join(staged), "|".join(untracked), config.model_dump_json()]
        for rel in sorted(set(changed + staged + untracked)):
            candidate = repo_root / rel
            if candidate.exists() and candidate.is_file():
                digest_parts.append(rel)
                digest_parts.append(hash_file(candidate))
        worktree_snapshot_id = f"dirty:{hash_text('|'.join(digest_parts), length=24)}"
    return GitMetadata(
        is_git=True,
        git_sha=git_sha,
        branch=branch,
        dirty=dirty,
        changed_files=changed,
        staged_files=staged,
        untracked_files=untracked,
        worktree_snapshot_id=worktree_snapshot_id,
    )


def capture_snapshot(repo_id: str, repo_root: Path, config: IndexingConfig, *, force_status: IndexStatus | None = None) -> tuple[SnapshotRef, str, GitMetadata]:
    metadata = collect_git_metadata(repo_root, repo_id, config)
    if metadata.is_git:
        snapshot = SnapshotRef(
            repo_id=repo_id,
            git_sha=metadata.git_sha,
            branch=metadata.branch,
            worktree_snapshot_id=metadata.worktree_snapshot_id,
            dirty=metadata.dirty,
            index_status=force_status or IndexStatus.FRESH,
            captured_ts=_now_ts(),
        )
    else:
        snapshot = SnapshotRef(
            repo_id=repo_id,
            git_sha=None,
            branch=None,
            worktree_snapshot_id=f"nogit:{hash_text(str(repo_root), length=24)}",
            dirty=True,
            index_status=force_status or IndexStatus.UNKNOWN,
            captured_ts=_now_ts(),
        )
    return snapshot, snapshot_id_for(snapshot), metadata


def changed_files_since_latest(repo_root: Path, metadata: GitMetadata) -> list[str]:
    if metadata.is_git:
        return sorted(set(metadata.changed_files + metadata.staged_files + metadata.untracked_files))
    return []
