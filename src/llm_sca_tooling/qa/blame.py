"""Typed cached git-blame lookup for QA and MCP tools."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from urllib.parse import unquote

from pydantic import Field

from llm_sca_tooling.indexing.blame import BlameChain
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.schemas.enums import ArtifactKind
from llm_sca_tooling.storage.workspace import WorkspaceStore


class BlameEntry(StrictBaseModel):
    start_line: int
    end_line: int
    commit_sha: str
    author_name: str | None = None
    author_email: str | None = None
    author_ts: str | None = None
    committer_ts: str | None = None
    summary: str | None = None
    body: str | None = None
    original_file: str | None = None
    original_line: int | None = None


class CommitRecord(StrictBaseModel):
    sha: str
    author_name: str | None = None
    author_ts: str | None = None
    summary: str | None = None
    parents: list[str] = Field(default_factory=list)


class FileHistoryEntry(StrictBaseModel):
    commit_sha: str
    file_path: str
    change_type: str
    author_name: str | None = None
    author_ts: str | None = None
    summary: str | None = None


class BlameChainResult(StrictBaseModel):
    repo_id: str
    file_path: str
    snapshot_id: str | None = None
    git_sha: str | None = None
    entries: list[BlameEntry] = Field(default_factory=list)
    commit_chain: list[CommitRecord] = Field(default_factory=list)
    file_history: list[FileHistoryEntry] = Field(default_factory=list)
    rename_chain: list[str] | None = None
    diagnostics: list[str] = Field(default_factory=list)
    run_event_ids: list[str] = Field(default_factory=list)


class BlameLookup:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace

    def lookup(self, repo_id: str, file_path: str, *, line: int | None = None, line_range: tuple[int, int] | None = None, follow_renames: bool = True, depth: int = 3) -> BlameChainResult:
        file_path = _decode_repo_relative_path(file_path)
        chain = self._cached_chain(repo_id, file_path)
        repo = self.workspace.repositories.get_repo(repo_id)
        if chain is None:
            path = Path(repo.root_path) / file_path
            diagnostics = ["blame_cache_miss"]
            if not path.exists():
                diagnostics.append("untracked")
            elif path.is_file() and _is_binary(path):
                diagnostics.append("binary_file")
            return BlameChainResult(repo_id=repo.repo_id, file_path=file_path, diagnostics=diagnostics)
        entries = [_entry_from_line(item.model_dump(mode="json")) for item in chain.line_entries]
        if line is not None:
            entries = [entry for entry in entries if entry.start_line <= line <= entry.end_line]
        if line_range is not None:
            start, end = line_range
            entries = [entry for entry in entries if entry.end_line >= start and entry.start_line <= end]
        commit_chain = [_commit_from_payload(item) for item in chain.commit_chain[:depth]]
        history = _file_history(Path(repo.root_path), file_path, depth) if follow_renames else []
        rename_chain = sorted({entry.file_path for entry in history if entry.file_path != file_path}) or None
        return BlameChainResult(repo_id=repo.repo_id, file_path=file_path, snapshot_id=chain.snapshot_id, git_sha=chain.git_sha, entries=entries, commit_chain=commit_chain, file_history=history, rename_chain=rename_chain, diagnostics=[diagnostic.code for diagnostic in chain.diagnostics])

    def _cached_chain(self, repo_id: str, file_path: str) -> BlameChain | None:
        for artifact in self.workspace.artifacts.list_artifacts(repo_id=repo_id, kind=ArtifactKind.REPORT.value):
            if not artifact.artifact_id.startswith("art:blame:"):
                continue
            path = Path(artifact.uri)
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("repo_id") == repo_id and payload.get("file_path") == file_path:
                return BlameChain.model_validate(payload)
        return None


def _entry_from_line(payload: dict[str, object]) -> BlameEntry:
    return BlameEntry(
        start_line=int(payload.get("line_no") or 0),
        end_line=int(payload.get("line_no") or 0),
        commit_sha=str(payload.get("commit_sha") or ""),
        author_ts=str(payload.get("author_time")) if payload.get("author_time") is not None else None,
        summary=str(payload.get("summary")) if payload.get("summary") is not None else None,
        original_file=str(payload.get("original_file_path")) if payload.get("original_file_path") is not None else None,
        original_line=int(payload["original_line_no"]) if payload.get("original_line_no") is not None else None,
    )


def _commit_from_payload(payload: dict[str, object]) -> CommitRecord:
    return CommitRecord(sha=str(payload.get("sha") or payload.get("commit_sha") or ""), author_name=str(payload.get("author_name")) if payload.get("author_name") else None, author_ts=str(payload.get("author_ts")) if payload.get("author_ts") else None, summary=str(payload.get("summary")) if payload.get("summary") else None, parents=[str(item) for item in payload.get("parents", [])] if isinstance(payload.get("parents"), list) else [])


def _file_history(repo_root: Path, file_path: str, depth: int) -> list[FileHistoryEntry]:
    try:
        result = subprocess.run(["git", "-C", str(repo_root), "log", "--follow", f"-n{depth}", "--name-status", "--format=%H%x1f%an%x1f%aI%x1f%s", "--", file_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []
    entries: list[FileHistoryEntry] = []
    current: tuple[str, str | None, str | None, str | None] | None = None
    for line_text in result.stdout.splitlines():
        if "\x1f" in line_text:
            parts = line_text.split("\x1f")
            current = (parts[0], parts[1] if len(parts) > 1 else None, parts[2] if len(parts) > 2 else None, parts[3] if len(parts) > 3 else None)
        elif current and line_text:
            cols = line_text.split("\t")
            change = cols[0]
            path = cols[-1] if cols else file_path
            entries.append(FileHistoryEntry(commit_sha=current[0], file_path=path, change_type=_change_type(change), author_name=current[1], author_ts=current[2], summary=current[3]))
    return entries


def _change_type(status: str) -> str:
    if status.startswith("R"):
        return "renamed"
    return {"A": "added", "M": "modified", "D": "deleted"}.get(status[:1], status.lower() or "unknown")


def _is_binary(path: Path) -> bool:
    try:
        return b"\0" in path.read_bytes()[:2048]
    except OSError:
        return False


def _decode_repo_relative_path(value: str) -> str:
    decoded = unquote(value).lstrip("/")
    if not decoded or "\\" in decoded or any(part in {"", ".", ".."} for part in decoded.split("/")):
        raise ValueError("file path must be repo-relative")
    return decoded
