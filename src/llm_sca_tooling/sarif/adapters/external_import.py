"""External SARIF file importer."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.sarif.models import NormalizedSarifRun
from llm_sca_tooling.sarif.normalizer import normalize_sarif_log
from llm_sca_tooling.sarif.parser import parse_sarif_file

__all__ = ["ExternalSarifImporter"]


class ExternalSarifImporter:
    def import_sarif_file(
        self,
        file_path: Path,
        *,
        repo_root: Path,
        repo_id: str,
        snapshot_id: str,
        git_sha: str,
        run_id: str,
        analyser_hint: str | None = None,
        artifact_ref: str | None = None,
    ) -> NormalizedSarifRun:
        log = parse_sarif_file(file_path, repo_root=repo_root)
        return normalize_sarif_log(
            log,
            repo_id=repo_id,
            snapshot_id=snapshot_id,
            git_sha=git_sha,
            run_id=run_id,
            analyser_id=analyser_hint or "external",
            raw_sarif_artifact_ref=artifact_ref,
        )
