"""SARIF reference models.

Phase 1 does not parse SARIF files.  It defines references to SARIF runs and
alerts that later phases bind to graph nodes.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field

from llm_sca_tooling.schemas.base import NonEmptyStr, StrictModel
from llm_sca_tooling.schemas.provenance import (
    ArtifactRef,
    Provenance,
    RepoRef,
    SnapshotRef,
    SourceSpan,
)

__all__ = ["SarifSeverity", "SarifRunRef", "SarifAlertRef"]


class SarifSeverity(str, Enum):
    error = "error"
    warning = "warning"
    note = "note"
    none = "none"
    unknown = "unknown"


class SarifRunRef(StrictModel):
    sarif_run_id: NonEmptyStr
    repo: RepoRef
    snapshot: SnapshotRef
    analyzer_name: NonEmptyStr
    analyzer_version: str | None = None
    ruleset: str | None = None
    artifact_ref: ArtifactRef | None = None
    provenance: Provenance


class SarifAlertRef(StrictModel):
    alert_id: NonEmptyStr
    sarif_run_id: NonEmptyStr
    rule_id: NonEmptyStr
    predicate_id: str | None = None
    severity: SarifSeverity = SarifSeverity.unknown
    level: str | None = None
    locations: list[SourceSpan] = Field(default_factory=list)
    bound_node_ids: list[str] = Field(default_factory=list)
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = 1.0
    provenance: Provenance
