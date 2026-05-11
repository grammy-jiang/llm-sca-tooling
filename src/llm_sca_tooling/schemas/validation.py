"""Validation helpers for cross-model invariants.

These helpers are called by workflow phases, operational review, and tests.
They do NOT modify models; they report violations as lists of strings.
"""

from __future__ import annotations

from llm_sca_tooling.schemas.evidence import EvidenceBundle
from llm_sca_tooling.schemas.graph import GraphDocument, check_edge_endpoints
from llm_sca_tooling.schemas.provenance import EvidenceStrength, Provenance
from llm_sca_tooling.schemas.run_records import (
    RunEvent,
    RunRecord,
    RunStatus,
    validate_event_sequence,
)
from llm_sca_tooling.schemas.verdicts import _POSITIVE_VERDICTS, Verdict, VerdictValue

__all__ = [
    "validate_provenance_completeness",
    "validate_graph_document",
    "validate_run_sequence",
    "validate_evidence_bundle",
    "validate_verdict",
    "validate_snapshot_consistency",
]


def validate_provenance_completeness(prov: Provenance) -> list[str]:
    """Return a list of provenance violation messages."""
    errors: list[str] = []
    if not prov.source_tool:
        errors.append("provenance.source_tool is missing")
    if prov.repo.repo_id != prov.snapshot.repo_id:
        errors.append(
            f"provenance repo_id {prov.repo.repo_id!r} != "
            f"snapshot repo_id {prov.snapshot.repo_id!r}"
        )
    if not (0.0 <= prov.confidence <= 1.0):
        errors.append(f"provenance.confidence {prov.confidence} outside [0, 1]")
    return errors


def validate_graph_document(doc: GraphDocument) -> list[str]:
    """Validate edge endpoints, provenance, and repo/snapshot consistency."""
    errors: list[str] = []
    node_ids = {n.node_id: n.node_type for n in doc.nodes}

    for edge in doc.edges:
        src_type = node_ids.get(edge.source_id)
        tgt_type = node_ids.get(edge.target_id)
        if src_type is None:
            errors.append(
                f"edge {edge.edge_id!r}: source_id {edge.source_id!r} not in document"
            )
        if tgt_type is None:
            errors.append(
                f"edge {edge.edge_id!r}: target_id {edge.target_id!r} not in document"
            )
        if src_type and tgt_type:
            err = check_edge_endpoints(edge.edge_type, src_type, tgt_type)
            if err:
                errors.append(f"edge {edge.edge_id!r}: {err}")

    if doc.has_mixed_snapshots():
        errors.append("graph document has mixed snapshots — must be marked explicitly")

    return errors


def validate_run_sequence(record: RunRecord, events: list[RunEvent]) -> list[str]:
    """Validate run record + event list for sequence, redaction, and completeness."""
    errors = validate_event_sequence(events, record.run_id)

    for event in events:
        if event.redaction_status is None:
            errors.append(f"event {event.event_id!r} missing redaction_status")

    if record.status == RunStatus.completed:
        if record.end_ts is None:
            errors.append("completed run missing end_ts")
        if record.harness_condition_id is None:
            errors.append(
                "completed run missing harness_condition_id (operationally incomplete)"
            )

    return errors


def validate_evidence_bundle(bundle: EvidenceBundle) -> list[str]:
    """Validate evidence bundle consistency."""
    errors: list[str] = []
    if bundle.is_only_soft_llm and bundle.evidence_items:
        errors.append(
            f"bundle {bundle.bundle_id!r}: all evidence is soft_llm — "
            "downstream verdicts must be unknown or include harder evidence"
        )
    return errors


def validate_verdict(verdict: Verdict) -> list[str]:
    """Validate verdict evidence strength constraints."""
    errors: list[str] = []
    if verdict.verdict in _POSITIVE_VERDICTS and verdict.reasoning_chain:
        all_soft = all(
            s.strength == EvidenceStrength.soft_llm for s in verdict.reasoning_chain
        )
        if all_soft:
            errors.append(
                f"verdict {verdict.verdict_id!r}: positive verdict backed "
                "only by soft_llm evidence"
            )
    if verdict.verdict == VerdictValue.unknown and not verdict.uncertainty:
        errors.append(
            f"verdict {verdict.verdict_id!r}: unknown verdict "
            "has no uncertainty reasons"
        )
    return errors


def validate_snapshot_consistency(doc: GraphDocument) -> list[str]:
    """Return messages about mixed or dirty snapshot evidence."""
    errors: list[str] = []
    if doc.snapshot.dirty:
        errors.append(
            f"graph {doc.graph_id!r}: base snapshot is dirty — evidence may be stale"
        )
    if doc.has_mixed_snapshots():
        errors.append(
            f"graph {doc.graph_id!r}: nodes or edges reference different snapshots"
        )
    return errors
