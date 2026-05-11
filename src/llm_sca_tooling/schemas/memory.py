"""Memory reference models.

Phase 1 defines enough schema surface for later trajectory and retention
work.  Phase 17 implements memory retrieval and compaction.
"""

from __future__ import annotations

from enum import Enum

from llm_sca_tooling.schemas.base import NonEmptyStr, StrictModel
from llm_sca_tooling.schemas.provenance import Provenance, RedactionStatus, RepoRef

__all__ = ["RetentionClass", "TrajectoryRef", "RetentionPolicy"]


class RetentionClass(str, Enum):
    ephemeral = "ephemeral"
    session = "session"
    project = "project"
    permanent = "permanent"


class TrajectoryRef(StrictModel):
    trajectory_id: NonEmptyStr
    repo: RepoRef
    issue_ref: str | None = None
    source_run_id: NonEmptyStr
    fl_decision_refs: list[str] = []
    graph_slice_refs: list[str] = []
    patch_ref: str | None = None
    sarif_delta_ref: str | None = None
    test_result_refs: list[str] = []
    outcome_ref: str | None = None
    utility: float = 0.0
    retention: RetentionClass = RetentionClass.session
    provenance: Provenance


class RetentionPolicy(StrictModel):
    retention_class: RetentionClass = RetentionClass.session
    expires_ts: str | None = None
    review_due_ts: str | None = None
    owner: str | None = None
    exportable: bool = False
    delete_supported: bool = True
    redaction_status: RedactionStatus = RedactionStatus.not_required
    rollback_path: str | None = None
