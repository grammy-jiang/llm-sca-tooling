"""Git metadata collector using asyncio subprocesses.

All git commands use asyncio.create_subprocess_exec (argument arrays, no shell=True)
to prevent command injection. File paths are passed as separate arguments.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity, IndexingDiagnostic
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["GitMetadata", "GitMetadataCollector"]

logger = get_logger(__name__)


@dataclass
class GitMetadata:
    is_git_repo: bool
    git_sha: str | None
    branch: str | None
    dirty: bool
    changed_files: list[str]
    untracked_files: list[str]
    diagnostics: list[IndexingDiagnostic] = field(default_factory=list)


async def _run_git(args: list[str], cwd: Path) -> tuple[str, str, int]:
    """Run a git command with separate arguments (no shell) and return (stdout, stderr, rc)."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    rc = proc.returncode if proc.returncode is not None else 1
    return (
        stdout_bytes.decode(errors="replace").strip(),
        stderr_bytes.decode(errors="replace").strip(),
        rc,
    )


class GitMetadataCollector:
    """Collect repository git state for snapshot capture."""

    async def collect(self, repo_root: Path) -> GitMetadata:
        diagnostics: list[IndexingDiagnostic] = []

        try:
            _, _, rc = await _run_git(["rev-parse", "--is-inside-work-tree"], repo_root)
            if rc != 0:
                return GitMetadata(
                    is_git_repo=False,
                    git_sha=None,
                    branch=None,
                    dirty=False,
                    changed_files=[],
                    untracked_files=[],
                    diagnostics=[
                        IndexingDiagnostic(
                            severity=DiagnosticSeverity.info,
                            code="GIT_NOT_AVAILABLE",
                            message="Not a git repository; using content-hash snapshot",
                        )
                    ],
                )
        except Exception as exc:
            return GitMetadata(
                is_git_repo=False,
                git_sha=None,
                branch=None,
                dirty=False,
                changed_files=[],
                untracked_files=[],
                diagnostics=[
                    IndexingDiagnostic(
                        severity=DiagnosticSeverity.warning,
                        code="GIT_EXEC_ERROR",
                        message=f"Git not found or failed: {exc}",
                    )
                ],
            )

        sha_out, _, _ = await _run_git(["rev-parse", "HEAD"], repo_root)
        git_sha = sha_out if sha_out else None

        branch_out, _, _ = await _run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"], repo_root
        )
        branch = branch_out if branch_out not in ("HEAD", "") else None

        status_out, _, _ = await _run_git(["status", "--porcelain=v1"], repo_root)
        changed_files: list[str] = []
        untracked_files: list[str] = []
        for line in status_out.splitlines():
            if not line.strip():
                continue
            xy = line[:2]
            rest = line[3:].strip()
            if xy.startswith("?"):
                untracked_files.append(rest)
            else:
                changed_files.append(rest)

        dirty = bool(changed_files or untracked_files)
        if dirty:
            diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.warning,
                    code="GIT_DIRTY_WORKTREE",
                    message=f"Dirty worktree: {len(changed_files)} changed, {len(untracked_files)} untracked",
                )
            )

        return GitMetadata(
            is_git_repo=True,
            git_sha=git_sha,
            branch=branch,
            dirty=dirty,
            changed_files=changed_files,
            untracked_files=untracked_files,
            diagnostics=diagnostics,
        )

    async def get_changed_files(self, repo_root: Path, base_sha: str) -> list[str]:
        """Return files changed since *base_sha*.  Uses argument array, not shell."""
        out, _, rc = await _run_git(
            ["diff", "--name-only", base_sha, "HEAD"], repo_root
        )
        if rc != 0:
            return []
        return [f.strip() for f in out.splitlines() if f.strip()]


def make_worktree_snapshot_id(
    repo_id: str,
    git_sha: str | None,
    changed_files: list[str],
    repo_root: Path | None = None,
) -> str:
    """Return a stable dirty-worktree snapshot ID."""
    content_parts: list[str] = []
    if repo_root is not None:
        for rel_path in sorted(changed_files):
            path = repo_root / rel_path
            if path.is_file():
                try:
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                except OSError:
                    digest = "unreadable"
                content_parts.append(f"{rel_path}:{digest}")
            else:
                content_parts.append(f"{rel_path}:missing")
    else:
        content_parts = sorted(changed_files)
    key = f"{repo_id}|{git_sha or ''}|{'|'.join(content_parts)}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    return f"snap:{repo_id}:dirty:{digest}"
