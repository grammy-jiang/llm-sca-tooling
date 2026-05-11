"""Git blame chain collector.

All git subprocess calls use asyncio.create_subprocess_exec with argument
arrays — never shell=True or string interpolation — to prevent injection.
Blame failures produce diagnostics but do not fail the indexing build.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from llm_sca_tooling.indexing.diagnostics import DiagnosticSeverity, IndexingDiagnostic
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["BlameLine", "BlameChain", "BlameCollector"]

logger = get_logger(__name__)


@dataclass
class BlameLine:
    line_no: int
    commit_sha: str
    author_time: str
    summary: str
    original_file_path: str
    original_line_no: int


@dataclass
class BlameChain:
    blame_id: str
    repo_id: str
    snapshot_id: str
    file_path: str
    git_sha: str | None
    worktree_snapshot_id: str | None
    line_entries: list[BlameLine] = field(default_factory=list)
    diagnostics: list[IndexingDiagnostic] = field(default_factory=list)


class BlameCollector:
    """Collect git blame for indexed files."""

    async def collect(
        self,
        repo_root: Path,
        file_path: str,
        repo_id: str,
        snapshot_id: str,
        git_sha: str | None = None,
        worktree_snapshot_id: str | None = None,
    ) -> BlameChain:
        blame_id = (
            "blame:"
            + hashlib.sha256(
                f"{repo_id}|{snapshot_id}|{file_path}".encode()
            ).hexdigest()[:16]
        )

        chain = BlameChain(
            blame_id=blame_id,
            repo_id=repo_id,
            snapshot_id=snapshot_id,
            file_path=file_path,
            git_sha=git_sha,
            worktree_snapshot_id=worktree_snapshot_id,
        )

        abs_path = repo_root / file_path
        if not abs_path.exists():
            chain.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.warning,
                    code="BLAME_FILE_NOT_FOUND",
                    message=f"File not found for blame: {file_path}",
                    file_path=file_path,
                )
            )
            return chain

        try:
            # Use argument array — file_path is a separate arg, never interpolated
            proc = await asyncio.create_subprocess_exec(
                "git",
                "blame",
                "--line-porcelain",
                "--",
                file_path,
                cwd=str(repo_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            rc = proc.returncode
        except TimeoutError:
            chain.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.warning,
                    code="BLAME_TIMEOUT",
                    message=f"git blame timed out for {file_path}",
                    file_path=file_path,
                )
            )
            return chain
        except Exception as exc:
            chain.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.warning,
                    code="BLAME_EXEC_ERROR",
                    message=f"git blame failed for {file_path}: {exc}",
                    file_path=file_path,
                )
            )
            return chain

        if rc != 0:
            err = stderr.decode(errors="replace").strip()
            chain.diagnostics.append(
                IndexingDiagnostic(
                    severity=DiagnosticSeverity.warning,
                    code="BLAME_GIT_ERROR",
                    message=f"git blame non-zero exit for {file_path}: {err}",
                    file_path=file_path,
                )
            )
            return chain

        lines = stdout.decode(errors="replace").splitlines()
        chain.line_entries = self._parse_porcelain(lines)
        return chain

    def _parse_porcelain(self, lines: list[str]) -> list[BlameLine]:
        entries: list[BlameLine] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if len(line) > 40 and line[40] == " ":
                parts = line.split()
                if len(parts) >= 3:
                    commit_sha = parts[0]
                    orig_line = int(parts[1]) if parts[1].isdigit() else 1
                    cur_line = int(parts[2]) if parts[2].isdigit() else 1
                    author_time = ""
                    summary = ""
                    orig_file = ""
                    j = i + 1
                    while j < len(lines) and not (
                        len(lines[j]) > 40 and lines[j][40] == " "
                    ):
                        if lines[j].startswith("author-time "):
                            author_time = lines[j].split(" ", 1)[1]
                        elif lines[j].startswith("summary "):
                            summary = lines[j].split(" ", 1)[1]
                        elif lines[j].startswith("filename "):
                            orig_file = lines[j].split(" ", 1)[1]
                        j += 1
                    entries.append(
                        BlameLine(
                            line_no=cur_line,
                            commit_sha=commit_sha,
                            author_time=author_time,
                            summary=summary,
                            original_file_path=orig_file,
                            original_line_no=orig_line,
                        )
                    )
                    i = j
                    continue
            i += 1
        return entries
