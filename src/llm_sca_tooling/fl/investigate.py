"""Investigate skill foundation for Phase 13."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.fl.localisation import get_relevant_files
from llm_sca_tooling.fl.models import ContextBundle, LocalisationResult, StrictFlModel
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = [
    "CandidateReasoningEntry",
    "InvestigateBudget",
    "InvestigateInput",
    "InvestigateOutput",
    "InvestigateProvenance",
    "investigate",
    "render_investigate_prompt",
]


class InvestigateBudget(StrictFlModel):
    max_files: int = 8
    max_symbols_per_file: int = 5
    max_context_tokens: int = 8000
    use_embedding: bool = True
    enable_cross_language: bool = True
    enable_sbfl: bool = False


class InvestigateInput(StrictFlModel):
    issue_text: str
    repos: list[str] | None = None
    budget: InvestigateBudget = Field(default_factory=InvestigateBudget)
    snapshot: str | None = None
    prior_localisation: LocalisationResult | None = None


class InvestigateProvenance(StrictFlModel):
    signals_run: list[str]
    signals_available: list[str]
    embedding_model: str | None = None
    graph_snapshot_ids: dict[str, str] = Field(default_factory=dict)
    sarif_run_ids: list[str] = Field(default_factory=list)
    blame_freshness: str = "unknown"
    sbfl_available: bool = False
    memory_phase: str = "stub"


class CandidateReasoningEntry(StrictFlModel):
    candidate_id: str
    file_path: str
    reasoning_chain: str
    derivation: str = "deterministic"
    evidence_citations: list[str] = Field(default_factory=list)


class InvestigateOutput(StrictFlModel):
    localisation_result: LocalisationResult
    context_bundle: ContextBundle
    reasoning_chains: list[CandidateReasoningEntry] = Field(default_factory=list)
    memory_hints_used: list[str] = Field(default_factory=list)
    memory_hints_rejected: list[str] = Field(default_factory=list)
    cross_language_hops: list[dict[str, object]] = Field(default_factory=list)
    provenance: InvestigateProvenance


async def investigate(
    workspace: WorkspaceStore, payload: InvestigateInput
) -> InvestigateOutput:
    result, context = await get_relevant_files(
        workspace,
        issue_text=payload.issue_text,
        repos=payload.repos,
        max_files=payload.budget.max_files,
        include_symbols=True,
        snapshot=payload.snapshot,
        use_embedding=payload.budget.use_embedding,
    )
    chains = [
        CandidateReasoningEntry(
            candidate_id=candidate.candidate_id,
            file_path=candidate.file_path,
            reasoning_chain=candidate.evidence_summary or "No evidence summary.",
            evidence_citations=[
                signal.source_refs[0]
                for signal in candidate.signals
                if signal.source_refs
            ],
        )
        for candidate in result.ranked_files
    ]
    return InvestigateOutput(
        localisation_result=result,
        context_bundle=context,
        reasoning_chains=chains,
        provenance=InvestigateProvenance(
            signals_run=["KEYWORD", "GRAPH_NEIGHBOUR", "EMBEDDING", "MEMORY_HINT"],
            signals_available=result.signals_used,
            graph_snapshot_ids=result.snapshot_ids,
            sbfl_available=payload.budget.enable_sbfl,
        ),
    )


def render_investigate_prompt(
    payload: InvestigateInput, result: LocalisationResult
) -> str:
    ranked = "\n".join(
        f"- {candidate.file_path}: {candidate.evidence_summary}"
        for candidate in result.ranked_files
    )
    return (
        "# Investigate: Fault Localisation\n\n"
        f"## Context\n- Issue: {payload.issue_text}\n- Repos: {payload.repos}\n\n"
        f"## Candidate ranking\n{ranked}\n\n"
        "## Constraints\n- Only cite file paths and symbol names from evidence.\n"
    )
