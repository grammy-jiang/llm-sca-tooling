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


__all__ = ["build_blast_radius_stub"]
