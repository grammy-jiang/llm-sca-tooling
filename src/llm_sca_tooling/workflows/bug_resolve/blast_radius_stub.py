"""Phase 13 blast-radius stub. Phase 15 hardens this into a service."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.workflows.bug_resolve.models import BlastRadiusStub


def build_blast_radius_stub(
    *,
    run_id: str,
    candidate_index: int,
    changed_symbol_ids: list[str],
    direct_callers: list[str] | None = None,
    downstream_tests: list[str] | None = None,
    interface_boundaries: list[str] | None = None,
    cross_language_candidates: list[str] | None = None,
    ambiguous_links: list[str] | None = None,
    confirmed_links: list[str] | None = None,
    diagnostics: list[dict[str, Any]] | None = None,
) -> BlastRadiusStub:
    """Two-hop traversal placeholder.

    The stub is always ``is_partial=True`` because Phase 13 does not implement
    the full cross-repo / cross-language graph traversal required by Phase 15.
    """
    callers = list(direct_callers or [])
    tests = list(downstream_tests or [])
    boundaries = list(interface_boundaries or [])
    cross_lang = list(cross_language_candidates or [])
    ambiguous = list(ambiguous_links or [])
    confirmed = list(confirmed_links or [])
    impact = len(callers) + len(tests) + len(boundaries) + len(cross_lang)
    return BlastRadiusStub(
        run_id=run_id,
        candidate_index=candidate_index,
        changed_symbol_ids=list(changed_symbol_ids),
        direct_callers=callers,
        downstream_tests=tests,
        interface_boundaries=boundaries,
        cross_language_candidates=cross_lang,
        ambiguous_links=ambiguous,
        confirmed_links=confirmed,
        local_impact_count=impact,
        is_partial=True,
        diagnostics=list(diagnostics or []),
    )


def build_blast_radius_from_report(
    *,
    run_id: str,
    candidate_index: int,
    changed_symbol_ids: list[str],
    report: Any,
) -> BlastRadiusStub:
    impact_groups = getattr(report, "impact_groups", {}) or {}
    direct_callers = _impact_node_ids(impact_groups.get("direct_callers", []))
    downstream_tests = _impact_node_ids(impact_groups.get("tests", []))
    interface_boundaries = _impact_node_ids(impact_groups.get("interfaces", []))
    cross_language_candidates = _impact_node_ids(impact_groups.get("services", []))
    confirmed_links = sorted(
        {
            *_impact_node_ids(impact_groups.get("downstream_behaviours", [])),
            *direct_callers,
            *downstream_tests,
            *interface_boundaries,
            *cross_language_candidates,
        }
    )
    ambiguous_links = [
        f"{getattr(link, 'source_node_id', '')}->{getattr(link, 'target_node_id', '')}"
        for link in getattr(report, "ambiguous_links", [])
    ]
    diagnostics: list[dict[str, Any]] = [
        {
            "code": "blast_radius_service_used",
            "report_id": getattr(report, "report_id", ""),
            "change_type": getattr(report, "change_type", "unknown"),
        }
    ]
    partial_reason = getattr(report, "partial_reason", "")
    if partial_reason:
        diagnostics.append({"code": "partial_blast_radius", "message": partial_reason})
    return BlastRadiusStub(
        run_id=run_id,
        candidate_index=candidate_index,
        changed_symbol_ids=list(changed_symbol_ids),
        direct_callers=direct_callers,
        downstream_tests=downstream_tests,
        interface_boundaries=interface_boundaries,
        cross_language_candidates=cross_language_candidates,
        ambiguous_links=ambiguous_links,
        confirmed_links=confirmed_links,
        local_impact_count=int(getattr(report, "confirmed_impact_count", 0)),
        is_partial=bool(getattr(report, "is_partial", False)),
        diagnostics=diagnostics,
    )


def _impact_node_ids(items: list[Any]) -> list[str]:
    out: list[str] = []
    for item in items:
        if isinstance(item, dict):
            node_id = item.get("node_id")
        else:
            node_id = getattr(item, "node_id", None)
        if isinstance(node_id, str) and node_id:
            out.append(node_id)
    return out


__all__ = ["build_blast_radius_from_report", "build_blast_radius_stub"]
