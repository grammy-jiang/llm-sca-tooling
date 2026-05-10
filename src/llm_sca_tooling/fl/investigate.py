"""Private investigate foundation consumed by later repair workflows."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from llm_sca_tooling.fl.issue import IssueText
from llm_sca_tooling.fl.localisation import LocalisationRequest, LocalisationService
from llm_sca_tooling.fl.models import (
    CandidateReasoningEntry,
    ContextBundle,
    LocalisationResult,
)
from llm_sca_tooling.fl.reasoning import CandidateReasoningInput, ReasoningChainScaffold
from llm_sca_tooling.schemas.base import StrictBaseModel
from llm_sca_tooling.storage.workspace import WorkspaceStore, _now_ts


class InvestigateBudget(StrictBaseModel):
    max_files: int = Field(default=8, ge=1, le=20)
    max_symbols_per_file: int = Field(default=5, ge=1)
    max_context_tokens: int = Field(default=8000, ge=1)
    use_embedding: bool = True
    enable_cross_language: bool = True
    enable_sbfl: bool = False


class InvestigateInput(StrictBaseModel):
    issue_text: str
    repos: list[str] | None = None
    budget: InvestigateBudget = Field(default_factory=InvestigateBudget)
    snapshot: str | None = None
    prior_localisation: LocalisationResult | None = None


class InvestigateProvenance(StrictBaseModel):
    signals_run: list[str] = Field(default_factory=list)
    signals_available: list[str] = Field(default_factory=list)
    embedding_model: str | None = None
    graph_snapshot_ids: dict[str, str] = Field(default_factory=dict)
    sarif_run_ids: list[str] = Field(default_factory=list)
    blame_freshness: str = "unknown"
    sbfl_available: bool = False
    memory_phase: str = "stub"


class InvestigateOutput(StrictBaseModel):
    localisation_result: LocalisationResult
    context_bundle: ContextBundle
    reasoning_chains: list[CandidateReasoningEntry] = Field(default_factory=list)
    memory_hints_used: list[str] = Field(default_factory=list)
    memory_hints_rejected: list[str] = Field(default_factory=list)
    cross_language_hops: list[dict[str, object]] = Field(default_factory=list)
    provenance: InvestigateProvenance


class InvestigateService:
    def __init__(self, workspace: WorkspaceStore) -> None:
        self.workspace = workspace

    def investigate(self, request: InvestigateInput) -> InvestigateOutput:
        localisation = LocalisationService(self.workspace).get_relevant_files(
            LocalisationRequest(
                issue_text=request.issue_text,
                repos=request.repos,
                max_files=request.budget.max_files,
                include_symbols=True,
                snapshot=request.snapshot,
                use_embedding=request.budget.use_embedding,
            )
        )
        if localisation.context_bundle is None:
            raise ValueError("localisation did not produce a context bundle")
        reasoning = _reasoning_entries(localisation)
        return InvestigateOutput(
            localisation_result=localisation,
            context_bundle=localisation.context_bundle,
            reasoning_chains=reasoning,
            memory_hints_used=localisation.memory_hints_used,
            memory_hints_rejected=localisation.memory_hints_rejected,
            cross_language_hops=[],
            provenance=InvestigateProvenance(
                signals_run=[signal.value for signal in localisation.signals_used],
                signals_available=[
                    signal.value for signal in localisation.signals_used
                ],
                embedding_model=None,
                graph_snapshot_ids=localisation.snapshot_ids,
                sarif_run_ids=_sarif_run_ids(localisation),
                blame_freshness=(
                    "available"
                    if "blame_history"
                    in {signal.value for signal in localisation.signals_used}
                    else "unavailable"
                ),
                sbfl_available="sbfl"
                in {signal.value for signal in localisation.signals_used},
                memory_phase="stub",
            ),
        )


def render_investigate_prompt(
    template_path: str | Path,
    *,
    issue_text_normalized: str,
    repos: list[str],
    budget: InvestigateBudget,
    context_bundle_summary: str,
    ranked_candidates_with_signals: str,
    min_agreement_signals: int = 2,
) -> str:
    template = Path(template_path).read_text(encoding="utf-8")
    return template.format(
        issue_text_normalized=issue_text_normalized,
        repos=", ".join(repos),
        budget=budget.model_dump(mode="json"),
        context_bundle_summary=context_bundle_summary,
        ranked_candidates_with_signals=ranked_candidates_with_signals,
        min_agreement_signals=min_agreement_signals,
    )


def _reasoning_entries(
    localisation: LocalisationResult,
) -> list[CandidateReasoningEntry]:
    if localisation.context_bundle is None:
        return []
    scaffold = ReasoningChainScaffold()
    entries: list[CandidateReasoningEntry] = []
    for context_entry in localisation.context_bundle.files:
        candidate = context_entry.candidate_file
        entries.append(
            scaffold.deterministic_chain(
                CandidateReasoningInput(
                    candidate_file=candidate,
                    context_entry=context_entry,
                    issue_text=localisation_to_issue_placeholder(),
                    signals_summary=candidate.evidence_summary or "",
                )
            )
        )
    return entries


def localisation_to_issue_placeholder() -> IssueText:
    return IssueText(
        issue_id="issue:investigate-output",
        raw_text="",
        normalized_text="",
        submitted_ts=_now_ts(),
    )


def _sarif_run_ids(localisation: LocalisationResult) -> list[str]:
    run_ids: list[str] = []
    for candidate in localisation.ranked_files:
        for signal in candidate.signals:
            if signal.signal_type.value == "sarif_proximity":
                run_ids.extend(
                    ref
                    for ref in signal.source_refs
                    if ref.startswith("sarif:") or ref.startswith("run:")
                )
    return list(dict.fromkeys(run_ids))
