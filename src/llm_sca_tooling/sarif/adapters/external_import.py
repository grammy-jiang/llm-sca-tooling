"""Import externally-produced SARIF without running an analyser."""

from __future__ import annotations

import uuid
from pathlib import Path

from llm_sca_tooling.sarif.models import NormalizedSarifRun
from llm_sca_tooling.sarif.normalizer import SarifNormalizer
from llm_sca_tooling.sarif.parser import SarifParser
from llm_sca_tooling.storage.workspace import WorkspaceStore


class ExternalSarifImporter:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace

    def import_sarif_file(
        self,
        file_path: Path,
        *,
        repo_id: str,
        snapshot_id: str,
        git_sha: str | None,
        worktree_snapshot_id: str | None = None,
        analyser_hint: str | None = None,
    ) -> NormalizedSarifRun:
        artifact = self.workspace.sarif.record_raw_sarif_artifact(file_path)
        self.workspace.artifacts.record_artifact(
            artifact, repo_id=repo_id, run_id=None, payload_path=file_path
        )
        repo_root = self.workspace.repositories.get_repo(repo_id).root_path
        log = SarifParser().parse_file(file_path, repo_root=repo_root)
        run = SarifNormalizer().normalize(
            log,
            repo_id=repo_id,
            snapshot_id=snapshot_id,
            git_sha=git_sha,
            worktree_snapshot_id=worktree_snapshot_id,
            run_id=f"sarif:{uuid.uuid4().hex}",
            analyser_hint=analyser_hint,
            raw_sarif_artifact_ref=artifact,
        )
        return run.model_copy(
            update={
                "invocation_diagnostics": [
                    *run.invocation_diagnostics,
                    "external_import",
                ]
            },
            deep=True,
        )
