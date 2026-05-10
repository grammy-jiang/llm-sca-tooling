"""Phase 15 BlastRadiusReport assembler."""

from __future__ import annotations

from datetime import UTC, datetime

from llm_sca_tooling.blast_radius.models import (
    ABIImpactNote,
    AmbiguousLinkRecord,
    BlastRadiusReport,
    CrossRepoImpactRecord,
    GeneratedStubImpactNote,
    ImpactGroup,
    ImpactRecord,
)
from llm_sca_tooling.indexing.hashing import hash_text


def _now_ts() -> str:
    return datetime.now(UTC).isoformat()


def assemble_report(
    *,
    diff_id: str,
    run_id: str,
    change_type: str,
    traversal_policy_ref: str,
    confirmed_records: list[ImpactRecord],
    ambiguous_links: list[AmbiguousLinkRecord],
    generated_stub_notes: list[GeneratedStubImpactNote],
    abi_impact_notes: list[ABIImpactNote],
    cross_repo_impact_records: list[CrossRepoImpactRecord],
    sarif_summary: str = "",
    linked_docs_summary: str = "",
    is_partial: bool = False,
    partial_reason: str = "",
) -> BlastRadiusReport:
    """Assemble all sub-components into a BlastRadiusReport."""
    # Group confirmed records
    groups: dict[str, list[object]] = {g.value: [] for g in ImpactGroup}
    for rec in confirmed_records:
        groups[rec.group.value].append(rec.model_dump(mode="json"))

    confirmed_count = len(confirmed_records)
    ambiguous_count = len(ambiguous_links)

    # Determine partial flag
    partial = is_partial
    partial_reasons: list[str] = []
    if partial_reason:
        partial_reasons.append(partial_reason)
    if any(r.is_partial for r in cross_repo_impact_records):
        partial = True
        partial_reasons.append("Cross-repo overlay incomplete.")
    any_abi_unknown = any(
        n.abi_change_type.value == "unknown" for n in abi_impact_notes
    )
    if any_abi_unknown:
        partial = True
        partial_reasons.append("C/C++ ABI analysis unavailable (clangd absent).")

    report_id = f"blast-radius:{hash_text(f'{diff_id}|{run_id}', length=32)}"

    human_summary = _build_human_summary(
        change_type=change_type,
        confirmed_count=confirmed_count,
        ambiguous_count=ambiguous_count,
        groups=groups,
        cross_repo_records=cross_repo_impact_records,
        is_partial=partial,
        partial_reason=" | ".join(partial_reasons),
    )

    return BlastRadiusReport(
        report_id=report_id,
        diff_id=diff_id,
        run_id=run_id,
        change_type=change_type,
        traversal_policy_ref=traversal_policy_ref,
        impact_groups=groups,
        confirmed_impact_count=confirmed_count,
        ambiguous_impact_count=ambiguous_count,
        generated_stub_notes=generated_stub_notes,
        abi_impact_notes=abi_impact_notes,
        cross_repo_impact_records=cross_repo_impact_records,
        ambiguous_links=ambiguous_links,
        is_partial=partial,
        partial_reason=" | ".join(partial_reasons),
        sarif_reachability_summary=sarif_summary,
        linked_docs_summary=linked_docs_summary,
        human_readable_summary=human_summary,
        created_ts=_now_ts(),
    )


def _build_human_summary(
    *,
    change_type: str,
    confirmed_count: int,
    ambiguous_count: int,
    groups: dict[str, list[object]],
    cross_repo_records: list[CrossRepoImpactRecord],
    is_partial: bool,
    partial_reason: str,
) -> str:
    lines = [
        f"Change type: {change_type}",
        f"Confirmed impact: {confirmed_count} node(s).",
        f"Ambiguous links: {ambiguous_count} (reported separately).",
    ]
    for group_name, items in groups.items():
        if items:
            lines.append(f"  {group_name}: {len(items)} node(s)")
    if cross_repo_records:
        cross_total = sum(len(r.consuming_node_ids) for r in cross_repo_records)
        lines.append(
            f"  cross_repo consumers: {cross_total} node(s) across {len(cross_repo_records)} repo(s)"
        )
    if is_partial:
        lines.append(f"PARTIAL: {partial_reason}")
    return "\n".join(lines)


__all__ = ["assemble_report"]
