"""Fault-localisation pipeline orchestration."""

from __future__ import annotations

from llm_sca_tooling.fl.context_assembler import assemble_context
from llm_sca_tooling.fl.embedding_adapters import NullEmbeddingAdapter
from llm_sca_tooling.fl.graph_expansion import expand_graph_neighbours
from llm_sca_tooling.fl.issue import normalize_issue_text
from llm_sca_tooling.fl.keyword_retrieval import keyword_retrieve
from llm_sca_tooling.fl.memory_stub import MemoryHintStub
from llm_sca_tooling.fl.models import ConfidenceLevel, ContextBundle, LocalisationResult
from llm_sca_tooling.fl.ranking import RankingPolicy, agreement_score
from llm_sca_tooling.fl.reasoning import symbol_candidates
from llm_sca_tooling.fl.uncertainty import apply_uncertainty
from llm_sca_tooling.storage.workspace import WorkspaceStore

__all__ = ["get_relevant_files"]


async def get_relevant_files(
    workspace: WorkspaceStore,
    *,
    issue_text: str,
    repos: list[str] | None = None,
    failing_tests: list[str] | None = None,
    coverage_path: str | None = None,
    max_files: int = 8,
    include_symbols: bool = False,
    snapshot: str | None = None,
    use_embedding: bool = True,
) -> tuple[LocalisationResult, ContextBundle]:
    del failing_tests, coverage_path, snapshot
    issue = normalize_issue_text(issue_text, repos=repos)
    keyword = await keyword_retrieve(workspace, issue, repos)
    graph = await expand_graph_neighbours(
        workspace, keyword[:3], max_expansion_files=20
    )
    memory = MemoryHintStub().retrieve_fl_hints(issue, 5)
    ranked = RankingPolicy().merge([keyword, graph], max_files=max_files)
    context = await assemble_context(workspace, issue, ranked, max_files=max_files)
    signals = [signal for candidate in ranked for signal in candidate.signals]
    score = agreement_score(signals)
    confidence = ConfidenceLevel.analyser if score >= 0.6 else ConfidenceLevel.heuristic
    symbols = symbol_candidates(ranked, context.files) if include_symbols else None
    result = LocalisationResult(
        ranked_files=ranked,
        ranked_symbols=symbols,
        agreement_score=score,
        confidence=confidence if ranked else ConfidenceLevel.unknown,
        signals_used=sorted({signal.signal_type.value for signal in signals}),
        signals_missing=(
            ["EMBEDDING"]
            if use_embedding and not NullEmbeddingAdapter().is_available()
            else []
        ),
        context_bundle_ref={"kind": "inline", "file_count": len(context.files)},
        run_event_ids=["fl:issue_normalized", "fl:ranked"],
        snapshot_ids=context.snapshot_ids,
    )
    result = apply_uncertainty(
        result,
        embedding_available=not result.signals_missing,
        budget_exceeded=context.is_over_budget,
        all_frames_unresolved=bool(issue.stack_trace_frames and not ranked),
    )
    if memory.hints_used:
        result.signals_used.append("MEMORY_HINT")
    return result, context
