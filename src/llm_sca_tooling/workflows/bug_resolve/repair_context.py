"""Repair context builder."""

from __future__ import annotations

from llm_sca_tooling.workflows.bug_resolve.models import (
    InvestigateResult,
    RepairContextRecord,
    WorkflowConfig,
)


def build_repair_context(
    *,
    run_id: str,
    candidate_index: int,
    investigate: InvestigateResult,
    config: WorkflowConfig,
) -> RepairContextRecord:
    suspects = investigate.top3_file_suspects or [
        c.get("file_path", "unknown") for c in investigate.ranked_candidates[:6]
    ]
    token_estimate = len(suspects) * 200
    return RepairContextRecord(
        run_id=run_id,
        candidate_index=candidate_index,
        file_suspects=suspects,
        graph_slices_ref=f"graph://slices/{run_id}/{candidate_index}",
        summaries_ref=f"summaries://{run_id}/{candidate_index}",
        snapshot_id=investigate.snapshot_id,
        language="python",
        context_tokens_estimate=token_estimate,
        budget_remaining=max(0, config.context_budget - token_estimate),
        provenance={"agreement_score": investigate.agreement_score},
    )
