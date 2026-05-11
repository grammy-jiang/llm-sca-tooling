"""Evidence bundle models.

Evidence bundles let workflows return auditable verdicts without embedding
large artefacts directly.  Mixed or stale evidence is always visible.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field

from llm_sca_tooling.schemas.base import NonEmptyStr, StrictModel
from llm_sca_tooling.schemas.provenance import ArtifactRef, EvidenceStrength, Provenance

__all__ = [
    "EvidenceSupport",
    "SnapshotConsistency",
    "EvidenceItem",
    "MissingEvidence",
    "StaleEvidence",
    "EvidenceBundle",
]


class EvidenceSupport(str, Enum):
    supports = "supports"
    contradicts = "contradicts"
    neutral = "neutral"
    context = "context"


class SnapshotConsistency(str, Enum):
    clean = "clean"
    dirty = "dirty"
    stale = "stale"
    mixed = "mixed"
    unknown = "unknown"


class EvidenceItem(StrictModel):
    evidence_id: NonEmptyStr
    kind: str
    supports: EvidenceSupport
    refs: list[str] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    strength: EvidenceStrength
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    provenance: Provenance
    notes: str | None = None


class MissingEvidence(StrictModel):
    evidence_id: NonEmptyStr
    required_for: str
    description: str
    forces_unknown: bool = False


class StaleEvidence(StrictModel):
    evidence_id: NonEmptyStr
    reason: str
    stale_refs: list[str] = Field(default_factory=list)
    forces_unknown: bool = False


class EvidenceBundle(StrictModel):
    """An auditable collection of evidence items for a verdict subject."""

    bundle_id: NonEmptyStr
    subject_ref: NonEmptyStr
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    missing_evidence: list[MissingEvidence] = Field(default_factory=list)
    stale_evidence: list[StaleEvidence] = Field(default_factory=list)
    aggregate_strength: EvidenceStrength = EvidenceStrength.soft_llm
    snapshot_consistency: SnapshotConsistency = SnapshotConsistency.unknown
    created_ts: NonEmptyStr
    provenance: Provenance

    @property
    def is_only_soft_llm(self) -> bool:
        """Return True when ALL evidence items have soft_llm strength."""
        if not self.evidence_items:
            return True
        return all(
            item.strength == EvidenceStrength.soft_llm for item in self.evidence_items
        )

    def weakest_strength(self) -> EvidenceStrength:
        """Return the weakest evidence strength across all items."""
        if not self.evidence_items:
            return EvidenceStrength.soft_llm
        return min(item.strength for item in self.evidence_items)
