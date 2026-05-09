"""Cross-model validation helpers."""

from __future__ import annotations

from enum import StrEnum

from llm_sca_tooling.schemas.enums import EvidenceStrength, IndexStatus, RedactionStatus, SnapshotConsistency
from llm_sca_tooling.schemas.evidence import EvidenceBundle
from llm_sca_tooling.schemas.graph import GraphDocument, has_mixed_snapshots, validate_graph_document
from llm_sca_tooling.schemas.provenance import ArtifactRef, Provenance, SnapshotRef
from llm_sca_tooling.schemas.run_records import RunEvent, RunRecord, validate_run_events
from llm_sca_tooling.schemas.verdicts import Verdict, validate_verdict_against_bundle


class ValidationMode(StrEnum):
    STRICT = "strict"
    COMPAT = "compat"
    FIXTURE = "fixture"


def validate_provenance_complete(provenance: Provenance) -> None:
    if not provenance.source_tool or not provenance.repo or not provenance.snapshot:
        raise ValueError("provenance requires source_tool, repo, and snapshot")
    if provenance.repo.repo_id != provenance.snapshot.repo_id:
        raise ValueError("provenance repo and snapshot must reference the same repo")


def snapshot_consistency(snapshot: SnapshotRef) -> SnapshotConsistency:
    if snapshot.index_status == IndexStatus.MIXED:
        return SnapshotConsistency.MIXED
    if snapshot.index_status == IndexStatus.STALE:
        return SnapshotConsistency.STALE
    if snapshot.dirty:
        return SnapshotConsistency.DIRTY
    if snapshot.index_status == IndexStatus.FRESH:
        return SnapshotConsistency.CLEAN
    return SnapshotConsistency.UNKNOWN


def validate_redaction_status(artifact: ArtifactRef) -> None:
    if artifact.redaction_status in {RedactionStatus.UNKNOWN, RedactionStatus.BLOCKED}:
        raise ValueError("artifact redaction status must be resolved before promotion")


def validate_evidence_bundle(bundle: EvidenceBundle) -> None:
    validate_provenance_complete(bundle.provenance)
    if bundle.aggregate_strength == EvidenceStrength.CALIBRATED_MODEL:
        calibrated = [item for item in bundle.evidence_items if item.strength == EvidenceStrength.CALIBRATED_MODEL]
        if not calibrated:
            raise ValueError("calibrated aggregate strength requires calibrated evidence items")


def validate_verdict(verdict: Verdict, bundle: EvidenceBundle | None = None) -> None:
    validate_provenance_complete(verdict.provenance)
    if bundle is not None:
        validate_verdict_against_bundle(verdict, bundle)


def validate_complete_graph(document: GraphDocument) -> None:
    validate_graph_document(document)


def validate_complete_run(record: RunRecord, events: list[RunEvent]) -> None:
    validate_run_events(record, events)


def graph_has_mixed_snapshots(document: GraphDocument) -> bool:
    return has_mixed_snapshots(document)


def assert_schema_version_compatible(actual: str, expected_major_minor: str = "0.1") -> None:
    if not actual.startswith(f"{expected_major_minor}."):
        raise ValueError(f"incompatible schema version: {actual}")
