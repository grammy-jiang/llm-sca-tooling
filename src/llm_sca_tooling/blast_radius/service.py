"""BlastRadiusService: full Phase 15 implementation."""

from __future__ import annotations

import uuid
from typing import Any

from llm_sca_tooling.blast_radius.abi_impact import compute_abi_impact
from llm_sca_tooling.blast_radius.ambiguous_links import make_cross_repo_unresolved
from llm_sca_tooling.blast_radius.change_type import classify_change_type
from llm_sca_tooling.blast_radius.cross_repo import traverse_cross_repo
from llm_sca_tooling.blast_radius.generated_stub import detect_generated_stub_notes
from llm_sca_tooling.blast_radius.graph_traversal import build_nx_graph, traverse
from llm_sca_tooling.blast_radius.impact_groups import group_impacts, groups_to_dict
from llm_sca_tooling.blast_radius.models import (
    BlastRadiusConfig,
    BlastRadiusReport,
    ChangeType,
    ImpactGroup,
)
from llm_sca_tooling.blast_radius.sarif_reachability import compute_sarif_reachability
from llm_sca_tooling.blast_radius.traversal_policy import policy_for


class BlastRadiusService:
    def __init__(self, config: BlastRadiusConfig | None = None) -> None:
        self._config = config or BlastRadiusConfig()

    def compute(
        self,
        diff_id: str,
        changed_symbol_ids: list[str],
        *,
        run_id: str | None = None,
        changed_file_paths: list[str] | None = None,
        graph_nodes: list[dict[str, Any]] | None = None,
        graph_edges: list[dict[str, Any]] | None = None,
        sarif_alert_nodes: list[dict[str, Any]] | None = None,
        registered_repos: list[str] | None = None,
        is_public_api: bool = False,
        has_security_context: bool = False,
        cpp_backend_available: bool = False,
    ) -> BlastRadiusReport:
        run_id = run_id or f"br:{uuid.uuid4().hex[:8]}"
        file_paths = changed_file_paths or []

        # Classify change type
        change_type, _applicable = classify_change_type(
            changed_symbol_ids,
            changed_file_paths=file_paths,
            is_public_api=is_public_api,
            has_security_context=has_security_context,
        )
        policy = policy_for(change_type)

        # Build NetworkX graph and traverse
        graph = build_nx_graph(graph_nodes or [], graph_edges or [])
        confirmed, ambiguous = traverse(
            graph,
            changed_symbol_ids,
            policy,
            analyser_threshold=self._config.analyser_confidence_threshold,
        )

        # SARIF reachability
        if policy.include_sarif_reachability:
            sarif_records = compute_sarif_reachability(
                changed_symbol_ids, sarif_alert_nodes
            )
            confirmed.extend(sarif_records)

        # Impact groups
        groups = group_impacts(confirmed)
        groups_dict = groups_to_dict(groups)

        # Generated-stub notes
        gen_notes = detect_generated_stub_notes(diff_id, file_paths)

        # ABI notes (always produce, fallback when unavailable)
        abi_notes = compute_abi_impact(
            changed_symbol_ids, cpp_backend_available=cpp_backend_available
        )
        is_partial = not cpp_backend_available and bool(changed_symbol_ids)

        # Cross-repo traversal
        cross_repo_records, cross_repo_partial = traverse_cross_repo(
            changed_symbol_ids,
            registered_repos=registered_repos,
            overlay_available=bool(registered_repos),
        )
        if cross_repo_partial:
            is_partial = True
            ambiguous.append(
                make_cross_repo_unresolved(
                    changed_symbol_ids[0] if changed_symbol_ids else "unknown",
                    "unregistered",
                )
            )

        # Summaries
        sarif_count = len(groups.get(ImpactGroup.sarif_reachability, []))
        sarif_summary = (
            f"{sarif_count} SARIF alerts reachable"
            if policy.include_sarif_reachability
            else "not_included"
        )

        partial_reason = ""
        if is_partial:
            reasons = []
            if not cpp_backend_available:
                reasons.append("cpp_backend_unavailable")
            if cross_repo_partial:
                reasons.append("cross_repo_overlay_unavailable")
            partial_reason = ";".join(reasons)

        confirmed_count = sum(len(v) for v in groups.values())
        summary = _build_summary(
            change_type, groups_dict, confirmed_count, len(ambiguous)
        )

        return BlastRadiusReport(
            report_id=f"br:{run_id}",
            diff_id=diff_id,
            run_id=run_id,
            change_type=change_type,
            traversal_policy_ref=f"policy:{change_type.value}",
            impact_groups=groups_dict,
            confirmed_impact_count=confirmed_count,
            ambiguous_impact_count=len(ambiguous),
            generated_stub_notes=gen_notes,
            abi_impact_notes=abi_notes,
            cross_repo_impact_records=cross_repo_records,
            ambiguous_links=ambiguous,
            is_partial=is_partial,
            partial_reason=partial_reason,
            sarif_reachability_summary=sarif_summary,
            linked_docs_summary="not_included",
            human_readable_summary=summary,
        )

    def compute_from_changed_symbols(
        self,
        symbol_ids: list[str],
        change_type: ChangeType | None = None,
        config: BlastRadiusConfig | None = None,
        *,
        run_id: str | None = None,
    ) -> BlastRadiusReport:
        diff_id = f"diff:{','.join(symbol_ids[:2])}"
        return self.compute(
            diff_id=diff_id,
            changed_symbol_ids=symbol_ids,
            run_id=run_id,
        )


def _build_summary(
    change_type: ChangeType,
    groups: dict[str, list[Any]],
    confirmed: int,
    ambiguous: int,
) -> str:
    group_counts = ", ".join(f"{k}: {len(v)}" for k, v in groups.items() if v)
    return (
        f"Change type: {change_type.value}. "
        f"Confirmed impact: {confirmed} nodes ({group_counts}). "
        f"Ambiguous links: {ambiguous}."
    )
