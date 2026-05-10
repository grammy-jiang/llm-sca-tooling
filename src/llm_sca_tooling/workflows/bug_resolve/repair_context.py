"""Repair context builder for the bug-resolve workflow."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import (
    InvestigateResult,
    RepairContextRecord,
)

# fl-context-2026 sweet spot for fault-localisation context windows.
DEFAULT_TOP_FILES = 6
EXPANDED_TOP_FILES = 10


def build_repair_context(
    *,
    run_id: str,
    candidate_index: int,
    investigate_result: InvestigateResult,
    context_budget: int,
    expand_to_ten: bool = False,
    language: str | None = None,
) -> RepairContextRecord:
    """Assemble a bounded context window from the investigate result."""
    if context_budget <= 0:
        raise ValueError("context_budget must be positive")
    cap = EXPANDED_TOP_FILES if expand_to_ten else DEFAULT_TOP_FILES
    suspects = investigate_result.top3_file_suspects[:cap]
    extras = [
        str(c.get("file_path", ""))
        for c in investigate_result.ranked_candidates
        if c.get("file_path")
    ]
    seen: set[str] = set(suspects)
    for path in extras:
        if len(suspects) >= cap:
            break
        if path and path not in seen:
            suspects.append(path)
            seen.add(path)

    estimate = max(0, len(suspects) * 800)
    if estimate > context_budget:
        estimate = context_budget
    remaining = max(0, context_budget - estimate)
    provenance: dict[str, object] = {
        "agreement_score": investigate_result.agreement_score,
        "stale_snapshot_flag": investigate_result.stale_snapshot_flag,
        "expanded": expand_to_ten,
        "cap": cap,
    }
    return RepairContextRecord(
        run_id=run_id,
        candidate_index=candidate_index,
        file_suspects=suspects,
        graph_slices_ref=[f"slice:{path}" for path in suspects],
        summaries_ref=[f"summary:{path}" for path in suspects],
        blame_chain_refs=[],
        sarif_alerts_in_scope=[],
        interface_contracts_ref=[],
        snapshot_id=investigate_result.snapshot_id,
        language=language,
        context_tokens_estimate=estimate,
        budget_remaining=remaining,
        provenance=provenance,
    )


__all__ = ["build_repair_context", "DEFAULT_TOP_FILES", "EXPANDED_TOP_FILES"]
