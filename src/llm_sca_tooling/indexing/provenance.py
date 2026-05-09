"""Indexing provenance helpers."""

from __future__ import annotations

from llm_sca_tooling.schemas.enums import DerivationType, EvidenceStrength
from llm_sca_tooling.schemas.provenance import Provenance, RepoRef, SnapshotRef, SourceSpan
from llm_sca_tooling.storage.workspace import _now_ts


def make_provenance(
    *,
    source_tool: str,
    repo: RepoRef,
    snapshot: SnapshotRef,
    derivation: DerivationType = DerivationType.PARSER,
    evidence_strength: EvidenceStrength = EvidenceStrength.HARD_STATIC,
    confidence: float = 1.0,
    source_run_id: str | None = None,
    source_event_id: str | None = None,
    file: str | None = None,
    span: SourceSpan | None = None,
    attributes: dict | None = None,
) -> Provenance:
    return Provenance(
        source_tool=source_tool,
        source_version="0.1.0",
        source_run_id=source_run_id,
        source_event_id=source_event_id,
        repo=repo,
        snapshot=snapshot,
        file=file,
        span=span,
        derivation=derivation,
        confidence=confidence,
        evidence_strength=evidence_strength,
        created_ts=_now_ts(),
        attributes=attributes or {},
    )
