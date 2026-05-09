"""Repository, snapshot, span, artefact, and provenance models."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from llm_sca_tooling.schemas.base import (
    JsonObject,
    SCHEMA_VERSION,
    StrictBaseModel,
    id_field,
    validate_confidence,
    validate_non_empty,
    validate_repo_relative_path,
)
from llm_sca_tooling.schemas.enums import (
    ArtifactKind,
    DerivationType,
    EvidenceStrength,
    IndexStatus,
    RedactionStatus,
)


class VersionedModel(StrictBaseModel):
    schema_version: str = SCHEMA_VERSION


class RepoRef(StrictBaseModel):
    repo_id: str = id_field("Stable repository identifier.")
    name: str | None = None
    root_ref: str | None = None
    remote_url_hash: str | None = None
    default_branch: str | None = None


class SnapshotRef(StrictBaseModel):
    repo_id: str = id_field("Repository identifier for this snapshot.")
    git_sha: str | None = None
    branch: str | None = None
    worktree_snapshot_id: str | None = None
    dirty: bool
    index_status: IndexStatus
    captured_ts: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_snapshot(self) -> "SnapshotRef":
        if self.dirty and not self.worktree_snapshot_id:
            raise ValueError("dirty snapshots require worktree_snapshot_id")
        if not self.dirty and self.index_status == IndexStatus.FRESH and not self.git_sha:
            raise ValueError("fresh clean snapshots require git_sha")
        return self


class SourceSpan(StrictBaseModel):
    file_path: str
    start_line: int = Field(ge=1)
    start_col: int | None = Field(default=None, ge=1)
    end_line: int = Field(ge=1)
    end_col: int | None = Field(default=None, ge=1)
    byte_start: int | None = Field(default=None, ge=0)
    byte_end: int | None = Field(default=None, ge=0)
    encoding: str | None = None

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, value: str) -> str:
        return validate_repo_relative_path(value)

    @model_validator(mode="after")
    def validate_ranges(self) -> "SourceSpan":
        if self.end_line < self.start_line:
            raise ValueError("end_line must be greater than or equal to start_line")
        if self.byte_start is not None and self.byte_end is not None and self.byte_end < self.byte_start:
            raise ValueError("byte_end must be greater than or equal to byte_start")
        return self


class ArtifactRef(StrictBaseModel):
    artifact_id: str = id_field("Stable artefact identifier.")
    kind: ArtifactKind
    uri: str = Field(min_length=1)
    sha256: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    media_type: str | None = None
    redaction_status: RedactionStatus
    created_ts: str | None = None


class Provenance(StrictBaseModel):
    source_tool: str = Field(min_length=1)
    source_version: str | None = None
    source_run_id: str | None = None
    source_event_id: str | None = None
    repo: RepoRef
    snapshot: SnapshotRef
    file: str | None = None
    span: SourceSpan | None = None
    derivation: DerivationType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_strength: EvidenceStrength
    created_ts: str = Field(min_length=1)
    attributes: JsonObject = Field(default_factory=dict)

    @field_validator("source_tool")
    @classmethod
    def validate_tool(cls, value: str) -> str:
        return validate_non_empty(value, "source_tool")

    @field_validator("file")
    @classmethod
    def validate_file(cls, value: str | None) -> str | None:
        return None if value is None else validate_repo_relative_path(value)

    @field_validator("confidence")
    @classmethod
    def validate_confidence_field(cls, value: float) -> float:
        return validate_confidence(value)

    @model_validator(mode="after")
    def validate_provenance(self) -> "Provenance":
        if self.repo.repo_id != self.snapshot.repo_id:
            raise ValueError("provenance repo.repo_id must match snapshot.repo_id")
        if self.derivation == DerivationType.LLM and self.evidence_strength in {
            EvidenceStrength.HARD_STATIC,
            EvidenceStrength.HARD_DYNAMIC,
        }:
            raise ValueError("LLM-derived provenance cannot claim hard evidence strength")
        return self
