"""Indexing result and context models."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from llm_sca_tooling.indexing.config import IndexingConfig
from llm_sca_tooling.indexing.diagnostics import IndexDiagnostic
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel


class IndexingResult(StrictBaseModel):
    repo_id: str
    run_id: str
    snapshot_id: str
    status: str
    files_scanned: int
    files_indexed: int
    files_skipped: int
    changed_files: list[str] = Field(default_factory=list)
    nodes_added: int
    edges_added: int
    diagnostics: list[IndexDiagnostic] = Field(default_factory=list)
    graph_manifest_id: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    stale_summary_count: int = 0
    backend_versions: dict[str, str] = Field(default_factory=dict)
    started_ts: str
    ended_ts: str


class IndexingContext(StrictBaseModel):
    repo_id: str
    repo_root: Path
    snapshot_id: str
    run_id: str
    config: IndexingConfig
    model_config = StrictBaseModel.model_config | {"arbitrary_types_allowed": True}


class IndexingPayload(StrictBaseModel):
    nodes_added: int
    edges_added: int
    backend_versions: dict[str, str] = Field(default_factory=dict)
    metadata: JsonObject = Field(default_factory=dict)
