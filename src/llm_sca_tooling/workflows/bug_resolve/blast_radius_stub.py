"""Blast-radius integration — delegates to Phase 15 BlastRadiusService."""

from __future__ import annotations

from llm_sca_tooling.blast_radius.service import BlastRadiusService
from llm_sca_tooling.workflows.bug_resolve.models import BlastRadiusStub, CandidatePatch

_service = BlastRadiusService()


def compute_blast_radius(patch: CandidatePatch) -> BlastRadiusStub:
    report = _service.compute(
        diff_id=f"diff:{patch.run_id}/{patch.candidate_index}",
        changed_symbol_ids=patch.changed_symbol_ids,
        run_id=patch.run_id,
    )
    return BlastRadiusStub(
        run_id=patch.run_id,
        candidate_index=patch.candidate_index,
        changed_symbol_ids=patch.changed_symbol_ids,
        direct_callers=[
            r["node_id"] for r in report.impact_groups.get("DIRECT_CALLERS", [])
        ],
        downstream_tests=[r["node_id"] for r in report.impact_groups.get("TESTS", [])],
        interface_boundaries=[
            r["node_id"] for r in report.impact_groups.get("INTERFACES", [])
        ],
        cross_language_candidates=[
            r["node_id"] for r in report.impact_groups.get("SERVICES", [])
        ],
        ambiguous_links=[link.target_node_id for link in report.ambiguous_links],
        confirmed_links=patch.changed_symbol_ids[:1],
        local_impact_count=max(
            report.confirmed_impact_count, len(patch.changed_symbol_ids)
        ),
        is_partial=report.is_partial,
        diagnostics=[
            (
                f"phase15: {report.partial_reason}"
                if report.is_partial
                else "phase15: full"
            )
        ],
    )
