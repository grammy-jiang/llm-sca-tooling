"""Provenance creation helpers for the indexing pipeline."""

from __future__ import annotations

from datetime import UTC, datetime

from llm_sca_tooling.schemas.provenance import (
    DerivationType,
    EvidenceStrength,
    Provenance,
    RepoRef,
    SnapshotRef,
    SourceSpan,
)

__all__ = [
    "make_provenance",
    "scanner_provenance",
    "parser_provenance",
    "heuristic_provenance",
]

_TOOL = "llm-sca-tooling.indexer"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def make_provenance(
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
    *,
    source_tool: str = _TOOL,
    source_version: str | None = None,
    derivation: DerivationType = DerivationType.parser,
    confidence: float = 1.0,
    evidence_strength: EvidenceStrength = EvidenceStrength.hard_static,
    file: str | None = None,
    span: SourceSpan | None = None,
) -> Provenance:
    return Provenance(
        source_tool=source_tool,
        source_version=source_version,
        repo=repo_ref,
        snapshot=snapshot_ref,
        derivation=derivation,
        confidence=confidence,
        evidence_strength=evidence_strength,
        file=file,
        span=span,
        created_ts=_now(),
    )


def scanner_provenance(repo_ref: RepoRef, snapshot_ref: SnapshotRef) -> Provenance:
    """Provenance for file-existence and containment facts (hard_static)."""
    return make_provenance(
        repo_ref,
        snapshot_ref,
        source_tool=f"{_TOOL}.scanner",
        derivation=DerivationType.parser,
        evidence_strength=EvidenceStrength.hard_static,
        confidence=1.0,
    )


def parser_provenance(
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
    backend_id: str,
    *,
    file: str | None = None,
    span: SourceSpan | None = None,
    confidence: float = 1.0,
) -> Provenance:
    """Provenance for symbol/import facts from a deterministic parser."""
    return make_provenance(
        repo_ref,
        snapshot_ref,
        source_tool=f"{_TOOL}.{backend_id}",
        derivation=DerivationType.parser,
        evidence_strength=EvidenceStrength.hard_static,
        confidence=confidence,
        file=file,
        span=span,
    )


def heuristic_provenance(
    repo_ref: RepoRef,
    snapshot_ref: SnapshotRef,
    backend_id: str,
    *,
    file: str | None = None,
    confidence: float = 0.7,
) -> Provenance:
    """Provenance for heuristic edges (test→symbol naming, etc.)."""
    return make_provenance(
        repo_ref,
        snapshot_ref,
        source_tool=f"{_TOOL}.{backend_id}",
        derivation=DerivationType.heuristic,
        evidence_strength=EvidenceStrength.structured_repository,
        confidence=confidence,
        file=file,
    )
