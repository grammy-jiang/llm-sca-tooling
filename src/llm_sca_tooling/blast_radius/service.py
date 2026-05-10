"""Phase 15 BlastRadiusService — replaces BlastRadiusStub from Phase 13."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from llm_sca_tooling.blast_radius.abi_impact import build_abi_impact_notes
from llm_sca_tooling.blast_radius.change_type import ChangeType, classify_change_type
from llm_sca_tooling.blast_radius.cross_repo import traverse_cross_repo
from llm_sca_tooling.blast_radius.doc_spec_impact import collect_linked_docs
from llm_sca_tooling.blast_radius.generated_stub import build_generated_stub_notes
from llm_sca_tooling.blast_radius.graph_traversal import traverse_graph
from llm_sca_tooling.blast_radius.models import (
    AmbiguousLinkRecord,
    BlastRadiusConfig,
    BlastRadiusReport,
    ImpactRecord,
)
from llm_sca_tooling.blast_radius.report import assemble_report
from llm_sca_tooling.blast_radius.sarif_reachability import collect_sarif_reachability
from llm_sca_tooling.blast_radius.traversal_policy import (
    TraversalPolicy,
    default_policy_for,
)
from llm_sca_tooling.patch_review.models import ChangedSymbolRecord

if TYPE_CHECKING:
    from llm_sca_tooling.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)


class BlastRadiusService:
    """Full Phase 15 blast-radius service.

    Replaces the Phase 13 BlastRadiusStub.
    """

    def __init__(
        self,
        graph_store: GraphStore,
        config: BlastRadiusConfig | None = None,
        *,
        registered_repo_ids: list[str] | None = None,
        clangd_available: bool = False,
        generated_file_allowlist: set[str] | None = None,
    ) -> None:
        self._graph_store = graph_store
        self._config = config or BlastRadiusConfig()
        self._registered_repo_ids = registered_repo_ids or []
        self._clangd_available = clangd_available
        self._generated_file_allowlist = generated_file_allowlist or set()

    async def compute_from_changed_symbols(
        self,
        symbol_records: list[ChangedSymbolRecord],
        *,
        diff_id: str,
        run_id: str,
        change_type_override: ChangeType | None = None,
        policy_override: TraversalPolicy | None = None,
    ) -> BlastRadiusReport:
        """Full blast-radius computation from ChangedSymbolRecord list."""
        cfg = self._config

        # 1. Classify change type
        primary_ct, applicable_cts = classify_change_type(symbol_records)
        if change_type_override is not None:
            primary_ct = change_type_override
            applicable_cts = [change_type_override]

        # 2. Select traversal policy
        policy = policy_override or default_policy_for(primary_ct, applicable_cts)

        # Apply config overrides
        max_hops = cfg.max_hops_override or policy.max_hops
        include_cross_lang = (
            cfg.include_cross_language_override
            if cfg.include_cross_language_override is not None
            else policy.include_cross_language
        )
        include_cross_repo = (
            cfg.include_cross_repo_override
            if cfg.include_cross_repo_override is not None
            else policy.include_cross_repo
        )
        effective_policy = TraversalPolicy(
            change_type=policy.change_type,
            max_hops=max_hops,
            follow_edge_types=policy.follow_edge_types,
            stop_at_interface_boundary=policy.stop_at_interface_boundary,
            include_cross_language=include_cross_lang,
            include_cross_repo=include_cross_repo,
            include_generated_files=policy.include_generated_files,
            include_test_nodes=cfg.include_test_nodes and policy.include_test_nodes,
            include_sarif_reachability=cfg.include_sarif_reachability
            and policy.include_sarif_reachability,
            include_doc_spec_links=cfg.include_doc_spec_links
            and policy.include_doc_spec_links,
            depth_multiplier_security=policy.depth_multiplier_security,
            confirmed_only=policy.confirmed_only,
        )

        # 3. Collect changed node IDs
        changed_node_ids = [r.graph_node_id for r in symbol_records if r.graph_node_id]

        # 4. BFS traversal (synchronous — SQLite graph_store is not thread-safe)
        confirmed_records, ambiguous_links = traverse_graph(
            changed_node_ids,
            self._graph_store,
            effective_policy,
            cfg.analyser_confidence_threshold,
            cfg.hub_dampening_threshold,
        )

        # 5. Generated-stub notes
        gen_notes = build_generated_stub_notes(
            diff_id,
            symbol_records,
            generated_file_allowlist=self._generated_file_allowlist,
        )

        # 6. ABI impact notes
        abi_notes = build_abi_impact_notes(
            symbol_records,
            clangd_available=self._clangd_available,
        )

        # 7. Cross-repo traversal
        cross_repo_records: list[ImpactRecord | object] = []
        cross_repo_ambiguous: list[AmbiguousLinkRecord] = []
        if include_cross_repo:
            xr_records, xr_ambig = traverse_cross_repo(
                changed_node_ids,
                self._graph_store,
                registered_repo_ids=self._registered_repo_ids,
                max_hops=max_hops,
                analyser_threshold=cfg.analyser_confidence_threshold,
            )
            cross_repo_records = xr_records  # type: ignore[assignment]
            cross_repo_ambiguous = xr_ambig
            ambiguous_links.extend(cross_repo_ambiguous)

        # 8. SARIF reachability
        sarif_alerts: list[dict[str, object]] = []
        sarif_summary = "SARIF reachability not included in this policy."
        if effective_policy.include_sarif_reachability and changed_node_ids:
            sarif_alerts, sarif_summary = collect_sarif_reachability(
                changed_node_ids,
                self._graph_store,
                max_hops=max_hops,
            )

        # 9. Linked docs/specs
        docs_summary = "Linked docs/specs not included in this policy."
        if effective_policy.include_doc_spec_links and changed_node_ids:
            _, docs_summary = collect_linked_docs(
                changed_node_ids,
                self._graph_store,
                max_hops=max_hops,
            )

        # 10. Determine partial flag
        is_partial = False
        partial_reason = ""
        if include_cross_repo and not self._registered_repo_ids:
            is_partial = True
            partial_reason = "No registered repos available for cross-repo traversal."

        # 11. Assemble report
        from llm_sca_tooling.blast_radius.models import (  # noqa: PLC0415
            CrossRepoImpactRecord,
        )

        return assemble_report(
            diff_id=diff_id,
            run_id=run_id,
            change_type=primary_ct.value,
            traversal_policy_ref=effective_policy.change_type.value,
            confirmed_records=confirmed_records,
            ambiguous_links=ambiguous_links,
            generated_stub_notes=gen_notes,
            abi_impact_notes=abi_notes,
            cross_repo_impact_records=[
                r for r in cross_repo_records if isinstance(r, CrossRepoImpactRecord)
            ],
            sarif_summary=sarif_summary,
            linked_docs_summary=docs_summary,
            is_partial=is_partial,
            partial_reason=partial_reason,
        )

    async def compute(
        self,
        diff_id: str,
        changed_symbol_records: list[ChangedSymbolRecord],
        *,
        run_id: str = "",
        config: BlastRadiusConfig | None = None,
    ) -> BlastRadiusReport:
        """Convenience wrapper: compute blast radius for a diff."""
        if config:
            # Temporarily swap config
            old_cfg = self._config
            self._config = config
            try:
                return await self.compute_from_changed_symbols(
                    changed_symbol_records,
                    diff_id=diff_id,
                    run_id=run_id or diff_id,
                )
            finally:
                self._config = old_cfg
        return await self.compute_from_changed_symbols(
            changed_symbol_records,
            diff_id=diff_id,
            run_id=run_id or diff_id,
        )


__all__ = ["BlastRadiusService"]
