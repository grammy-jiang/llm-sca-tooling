"""Memory reference contracts."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.schemas.base import StrictBaseModel, id_field
from llm_sca_tooling.schemas.enums import RedactionStatus
from llm_sca_tooling.schemas.provenance import Provenance, RepoRef


class RetentionPolicy(StrictBaseModel):
    retention_class: str = Field(min_length=1)
    expires_ts: str | None = None
    review_due_ts: str | None = None
    owner: str = Field(min_length=1)
    exportable: bool
    delete_supported: bool
    redaction_status: RedactionStatus
    rollback_path: str = Field(min_length=1)


class TrajectoryRef(StrictBaseModel):
    trajectory_id: str = id_field("Trajectory identifier.")
    repo: RepoRef
    issue_ref: str | None = None
    source_run_id: str = Field(min_length=1)
    fl_decision_refs: list[str] = Field(default_factory=list)
    graph_slice_refs: list[str] = Field(default_factory=list)
    patch_ref: str | None = None
    sarif_delta_ref: str | None = None
    test_result_refs: list[str] = Field(default_factory=list)
    outcome_ref: str | None = None
    utility: float = Field(ge=0.0, le=1.0)
    retention: RetentionPolicy
    provenance: Provenance
