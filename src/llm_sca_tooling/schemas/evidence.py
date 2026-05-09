"""Evidence bundle contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from llm_sca_tooling.schemas.base import SCHEMA_VERSION, StrictBaseModel, id_field
from llm_sca_tooling.schemas.enums import EvidenceStrength, SnapshotConsistency
from llm_sca_tooling.schemas.provenance import ArtifactRef, Provenance


class EvidenceSupport(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"
    CONTEXT = "context"


class EvidenceItem(StrictBaseModel):
    evidence_id: str = id_field("Evidence item identifier.")
    kind: str = Field(min_length=1)
    supports: EvidenceSupport
    refs: list[str] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    strength: EvidenceStrength
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: Provenance
    notes: str | None = None


class MissingEvidence(StrictBaseModel):
    missing_id: str = id_field("Missing evidence identifier.")
    expected_kind: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    affects_refs: list[str] = Field(default_factory=list)


class StaleEvidence(StrictBaseModel):
    stale_id: str = id_field("Stale evidence identifier.")
    evidence_ref: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    snapshot_ref: str | None = None


class EvidenceBundle(StrictBaseModel):
    schema_family: Literal["evidence"] = "evidence"
    schema_version: str = SCHEMA_VERSION
    bundle_id: str = id_field("Evidence bundle identifier.")
    subject_ref: str = Field(min_length=1)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    missing_evidence: list[MissingEvidence] = Field(default_factory=list)
    stale_evidence: list[StaleEvidence] = Field(default_factory=list)
    aggregate_strength: EvidenceStrength
    snapshot_consistency: SnapshotConsistency
    created_ts: str = Field(min_length=1)
    provenance: Provenance

    def has_only_soft_llm_support(self) -> bool:
        supports = [
            item
            for item in self.evidence_items
            if item.supports == EvidenceSupport.SUPPORTS
        ]
        return bool(supports) and all(
            item.strength == EvidenceStrength.SOFT_LLM for item in supports
        )
