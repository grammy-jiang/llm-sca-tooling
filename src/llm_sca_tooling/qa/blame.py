"""Git blame chain models and resource helper."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import Field

from llm_sca_tooling.qa.question import StrictQaModel

__all__ = ["BlameEntry", "BlameResource", "CommitRecord"]


class CommitRecord(StrictQaModel):
    commit_sha: str
    author: str
    author_time: str
    summary: str


class BlameEntry(StrictQaModel):
    repo_id: str
    file_path: str
    line_start: int
    line_end: int
    commit: CommitRecord
    snapshot_id: str | None = None


class BlameResource(StrictQaModel):
    entries: list[BlameEntry] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)

    @classmethod
    def from_git(
        cls,
        repo_root: Path,
        repo_id: str,
        file_path: str,
        *,
        line: int | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
        snapshot_id: str | None = None,
    ) -> BlameResource:
        target = repo_root / file_path
        if not target.exists():
            return cls(diagnostics=["UNTRACKED_OR_MISSING_FILE"])
        args = ["git", "-C", str(repo_root), "--no-pager", "blame", "--line-porcelain"]
        if line is not None:
            args.extend(["-L", f"{line},{line}"])
        elif start_line is not None or end_line is not None:
            start = start_line or 1
            end = end_line or start
            args.extend(["-L", f"{start},{end}"])
        args.append(file_path)
        try:
            proc = subprocess.run(  # noqa: S603
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            return cls(diagnostics=["BLAME_TIMEOUT"])
        if proc.returncode != 0:
            return cls(diagnostics=["BLAME_UNAVAILABLE"])
        return cls(
            entries=_parse_porcelain(proc.stdout, repo_id, file_path, snapshot_id)
        )


def _parse_porcelain(
    text: str, repo_id: str, file_path: str, snapshot_id: str | None
) -> list[BlameEntry]:
    entries: list[BlameEntry] = []
    current: dict[str, str] = {}
    line_no = 0
    for raw in text.splitlines():
        if raw.startswith("\t"):
            line_no += 1
            entries.append(
                BlameEntry(
                    repo_id=repo_id,
                    file_path=file_path,
                    line_start=line_no,
                    line_end=line_no,
                    snapshot_id=snapshot_id,
                    commit=CommitRecord(
                        commit_sha=current.get("sha", ""),
                        author=current.get("author", "unknown"),
                        author_time=current.get("author-time", ""),
                        summary=current.get("summary", ""),
                    ),
                )
            )
            continue
        parts = raw.split(" ", 1)
        if len(parts) == 2 and len(parts[0]) == 40:
            current = {"sha": parts[0]}
        elif len(parts) == 2:
            current[parts[0]] = parts[1]
    return entries
