"""Git blame-chain collector backed by artifacts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pydantic import Field

from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.indexing.hashing import hash_file, hash_text
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel
from llm_sca_tooling.schemas.enums import ArtifactKind, RedactionStatus, Severity
from llm_sca_tooling.schemas.provenance import (
    ArtifactRef,
    Provenance,
    RepoRef,
    SnapshotRef,
)
from llm_sca_tooling.storage.workspace import _now_ts


class BlameLine(StrictBaseModel):
    line_no: int
    commit_sha: str
    author_time: str | None = None
    summary: str | None = None
    original_file_path: str | None = None
    original_line_no: int | None = None


class BlameChain(StrictBaseModel):
    blame_id: str
    repo_id: str
    snapshot_id: str
    file_path: str
    git_sha: str | None
    worktree_snapshot_id: str | None
    line_entries: list[BlameLine] = Field(default_factory=list)
    commit_chain: list[JsonObject] = Field(default_factory=list)
    artifact_ref: ArtifactRef | None = None
    diagnostics: list[IndexDiagnostic] = Field(default_factory=list)
    provenance: Provenance


class BlameCollector:
    def collect(
        self,
        repo_root: Path,
        repo: RepoRef,
        snapshot_id: str,
        snapshot: SnapshotRef,
        file_path: str,
        provenance: Provenance,
        artifact_dir: Path,
    ) -> BlameChain:
        blame_id = f"blame:{hash_text(repo.repo_id + ':' + snapshot_id + ':' + file_path, length=24)}"
        chain = BlameChain(
            blame_id=blame_id,
            repo_id=repo.repo_id,
            snapshot_id=snapshot_id,
            file_path=file_path,
            git_sha=snapshot.git_sha,
            worktree_snapshot_id=snapshot.worktree_snapshot_id,
            provenance=provenance,
        )
        if not (repo_root / ".git").exists() or snapshot.dirty:
            chain.diagnostics.append(
                IndexDiagnostic(
                    diagnostic_id=f"diag:{blame_id}",
                    severity=Severity.WARNING,
                    code="blame_unavailable",
                    message="Blame unavailable for non-git or dirty snapshot",
                    file_path=file_path,
                )
            )
            return self._write_artifact(chain, artifact_dir)
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "blame",
                    "--line-porcelain",
                    "--",
                    file_path,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (
            OSError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as exc:
            chain.diagnostics.append(
                IndexDiagnostic(
                    diagnostic_id=f"diag:{blame_id}",
                    severity=Severity.WARNING,
                    code="blame_failed",
                    message=str(exc),
                    file_path=file_path,
                )
            )
            return self._write_artifact(chain, artifact_dir)
        current: dict[str, object] = {}
        line_no = 0
        for line in result.stdout.splitlines():
            if (
                line
                and not line.startswith("\t")
                and len(line.split()) >= 3
                and all(ch in "0123456789abcdef" for ch in line.split()[0][:8])
            ):
                line_no += 1
                current = {"commit_sha": line.split()[0], "line_no": line_no}
            elif line.startswith("author-time "):
                current["author_time"] = line.removeprefix("author-time ")
            elif line.startswith("summary "):
                current["summary"] = line.removeprefix("summary ")
            elif line.startswith("filename "):
                current["original_file_path"] = line.removeprefix("filename ")
            elif line.startswith("\t") and current:
                chain.line_entries.append(BlameLine.model_validate(current))
                current = {}
        return self._write_artifact(chain, artifact_dir)

    def _write_artifact(self, chain: BlameChain, artifact_dir: Path) -> BlameChain:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / f"{chain.blame_id.replace(':', '_')}.json"
        path.write_text(
            json.dumps(
                chain.model_dump(mode="json", exclude={"artifact_ref"}),
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        chain.artifact_ref = ArtifactRef(
            artifact_id=f"art:{chain.blame_id}",
            kind=ArtifactKind.REPORT,
            uri=str(path),
            sha256=hash_file(path),
            size_bytes=path.stat().st_size,
            media_type="application/json",
            redaction_status=RedactionStatus.REDACTED,
            created_ts=_now_ts(),
        )
        path.write_text(
            json.dumps(chain.model_dump(mode="json"), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return chain
