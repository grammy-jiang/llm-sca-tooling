"""SARIF run and alert reference contracts."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.schemas.base import StrictBaseModel, id_field
from llm_sca_tooling.schemas.enums import Severity
from llm_sca_tooling.schemas.provenance import (
    ArtifactRef,
    Provenance,
    RepoRef,
    SnapshotRef,
    SourceSpan,
)


class SarifRunRef(StrictBaseModel):
    sarif_run_id: str = id_field("SARIF run identifier.")
    repo: RepoRef
    snapshot: SnapshotRef
    analyzer_name: str = Field(min_length=1)
    analyzer_version: str | None = None
    ruleset: str | None = None
    artifact_ref: ArtifactRef | None = None
    provenance: Provenance


class SarifAlertRef(StrictBaseModel):
    alert_id: str = id_field("SARIF alert identifier.")
    sarif_run_id: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    predicate_id: str | None = None
    severity: Severity
    level: str | None = None
    locations: list[SourceSpan] = Field(default_factory=list)
    bound_node_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: Provenance
