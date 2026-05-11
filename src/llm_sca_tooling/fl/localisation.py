"""Fault-localisation orchestration service."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.fl.blame_prior import BlamePrior
from llm_sca_tooling.fl.context_assembler import BoundedContextAssembler
from llm_sca_tooling.fl.embedding_adapters.null_adapter import NullEmbeddingAdapter
from llm_sca_tooling.fl.embedding_interface import EmbeddingInterface
from llm_sca_tooling.fl.graph_expansion import GraphNeighbourExpander
from llm_sca_tooling.fl.issue import IssueText, normalize_issue_text
from llm_sca_tooling.fl.keyword_retrieval import KeywordRetriever
from llm_sca_tooling.fl.memory_stub import MemoryHintInterface, MemoryHintStub
from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    CandidateSymbol,
    ConfidenceLevel,
    ContextBundle,
    LocalisationResult,
    RetrievalDiagnostic,
    SignalType,
)
from llm_sca_tooling.fl.ranking import RankingPolicy
from llm_sca_tooling.fl.reasoning import (
    CandidateReasoningInput,
    FLSamplingClient,
    ReasoningChainScaffold,
)
from llm_sca_tooling.fl.sarif_prior import SarifPrior
from llm_sca_tooling.fl.sbfl import SbflPrior
from llm_sca_tooling.fl.uncertainty import UncertaintyModel
from llm_sca_tooling.schemas.base import JsonObject, StrictBaseModel
from llm_sca_tooling.storage.workspace import WorkspaceStore


class LocalisationRequest(StrictBaseModel):
    issue_text: str
    repos: list[str] | None = None
    failing_tests: list[str] | None = None
    coverage_path: str | None = None
    max_files: int | None = Field(default=None, ge=1, le=20)
    include_symbols: bool | None = False
    snapshot: str | None = None
    use_embedding: bool | None = True
    budget: JsonObject | None = None


class LocalisationService:
    def __init__(
        self,
        workspace: WorkspaceStore,
        *,
        embedding_adapter: EmbeddingInterface | None = None,
        memory: MemoryHintInterface | None = None,
        ranking_policy: RankingPolicy | None = None,
        sampling_client: FLSamplingClient | None = None,
    ) -> None:
        self.workspace = workspace
        self.embedding_adapter = embedding_adapter or NullEmbeddingAdapter()
        self.memory = memory or MemoryHintStub()
        self.ranking_policy = ranking_policy or RankingPolicy()
        self.sampling_client = sampling_client

    def get_relevant_files(self, request: LocalisationRequest) -> LocalisationResult:
        repos = self._repo_ids(request.repos)
        issue = normalize_issue_text(
            request.issue_text,
            repos=repos,
        )
        diagnostics: list[RetrievalDiagnostic] = []
        max_files = request.max_files or _budget_max_files(request.budget) or 8
        keyword_candidates = KeywordRetriever(self.workspace.graph).retrieve(
            issue,
            repo_ids=repos,
            max_results=50,
            snapshot_id=request.snapshot,
        )
        candidate_groups: list[list[CandidateFile]] = [keyword_candidates]
        available_signals = {SignalType.KEYWORD}
        if request.use_embedding and self.embedding_adapter.is_available():
            available_signals.add(SignalType.EMBEDDING)
            embedding_candidates, embedding_diagnostics = self._embedding_candidates(
                issue, repos
            )
            candidate_groups.append(embedding_candidates)
            diagnostics.extend(embedding_diagnostics)
        else:
            diagnostics.append(
                RetrievalDiagnostic(
                    code="EMBEDDING_UNAVAILABLE",
                    message="Embedding adapter is unavailable or disabled.",
                    severity="info",
                )
            )
        sarif_candidates, sarif_diagnostics = SarifPrior(self.workspace).retrieve(
            issue, repo_ids=repos
        )
        if sarif_candidates or sarif_diagnostics:
            available_signals.add(SignalType.SARIF_PROXIMITY)
            candidate_groups.append(sarif_candidates)
            diagnostics.extend(sarif_diagnostics)
        blame_candidates, blame_diagnostics = BlamePrior(self.workspace).retrieve(
            issue, repo_ids=repos
        )
        if blame_candidates or blame_diagnostics:
            available_signals.add(SignalType.BLAME_HISTORY)
            candidate_groups.append(blame_candidates)
            diagnostics.extend(blame_diagnostics)
        sbfl_candidates, sbfl_diagnostics = self._sbfl_candidates(request, repos)
        if sbfl_candidates:
            available_signals.add(SignalType.SBFL)
            candidate_groups.append(sbfl_candidates)
        diagnostics.extend(sbfl_diagnostics)
        memory_result = self.memory.retrieve_fl_hints(issue, max_hints=5)
        initial = self.ranking_policy.merge(
            candidate_groups,
            available_signals=available_signals,
            max_files=None,
        )
        graph_candidates = GraphNeighbourExpander(self.workspace.graph).expand(
            initial.ranked_files[:max_files],
            max_expansion_files=20,
        )
        if graph_candidates:
            available_signals.add(SignalType.GRAPH_NEIGHBOUR)
            candidate_groups.append(graph_candidates)
        ranked = self.ranking_policy.merge(
            candidate_groups,
            available_signals=available_signals,
            max_files=max_files,
        )
        context_bundle = BoundedContextAssembler(self.workspace).assemble(
            ranked.ranked_files,
            issue,
            max_files=max_files,
        )
        ranked_symbols = (
            self._symbols(ranked.ranked_files, issue, context_bundle)
            if request.include_symbols
            else None
        )
        stack_frames_resolved = _stack_frames_resolved(issue, ranked.ranked_files)
        base_confidence = (
            ranked.ranked_files[0].confidence
            if ranked.ranked_files
            else ConfidenceLevel.UNKNOWN
        )
        assessment = UncertaintyModel().evaluate(
            agreement_score=ranked.agreement_score,
            base_confidence=base_confidence,
            issue=issue,
            context_bundle=context_bundle,
            signals_missing=_signals_missing(available_signals),
            diagnostics=diagnostics,
            stack_frames_resolved=stack_frames_resolved,
        )
        return LocalisationResult(
            ranked_files=ranked.ranked_files,
            ranked_symbols=ranked_symbols,
            agreement_score=ranked.agreement_score,
            confidence=assessment.confidence,
            uncertainty=assessment.uncertainty,
            diagnostics=[
                diagnostic.model_dump(mode="json")
                for diagnostic in assessment.diagnostics
            ],
            signals_used=ranked.signals_used,
            signals_missing=_signals_missing(available_signals),
            context_bundle=context_bundle,
            snapshot_ids=context_bundle.snapshot_ids,
            memory_hints_used=[hint.hint_id for hint in memory_result.hints_used],
            memory_hints_rejected=[
                hint.hint_id for hint in memory_result.hints_rejected
            ],
        )

    def _repo_ids(self, requested: list[str] | None) -> list[str]:
        if requested:
            return [
                self.workspace.repositories.get_repo(repo).repo_id for repo in requested
            ]
        return [
            repo.repo_id
            for repo in self.workspace.repositories.list_repos(active_only=True)
        ]

    def _embedding_candidates(
        self, issue: IssueText, repo_ids: list[str]
    ) -> tuple[list[CandidateFile], list[RetrievalDiagnostic]]:
        _ = (issue, repo_ids)
        return [], [
            RetrievalDiagnostic(
                code="EMBEDDING_CACHE_EMPTY",
                message="Embedding retrieval is available but no vector-cache retrieval path produced candidates.",
                severity="info",
            )
        ]

    def _sbfl_candidates(
        self, request: LocalisationRequest, repo_ids: list[str]
    ) -> tuple[list[CandidateFile], list[RetrievalDiagnostic]]:
        if not repo_ids:
            return [], []
        snapshot = self.workspace.snapshots.get_latest_snapshot(repo_ids[0])
        return SbflPrior().retrieve(
            coverage_path=request.coverage_path,
            failing_tests=request.failing_tests,
            repo_id=repo_ids[0],
            snapshot_id=snapshot.snapshot_id if snapshot else "",
        )

    def _symbols(
        self,
        candidates: list[CandidateFile],
        issue: IssueText,
        context_bundle: ContextBundle,
    ) -> list[CandidateSymbol]:
        scaffold = ReasoningChainScaffold()
        symbols: list[CandidateSymbol] = []
        context_by_file = {
            entry.candidate_file.file_path: entry for entry in context_bundle.files
        }
        for candidate in candidates:
            nodes = self.workspace.graph.find_symbols(
                candidate.repo_id,
                file_path=candidate.file_path,
            )
            for node in nodes[:5]:
                entry = context_by_file.get(candidate.file_path)
                reasoning_chain = None
                if entry is not None:
                    if self.sampling_client is not None:
                        reasoning = scaffold.llm_chain(
                            CandidateReasoningInput(
                                candidate_file=candidate,
                                context_entry=entry,
                                issue_text=issue,
                                signals_summary=candidate.evidence_summary or "",
                            ),
                            self.sampling_client,
                        )
                    else:
                        reasoning = scaffold.deterministic_chain(
                            CandidateReasoningInput(
                                candidate_file=candidate,
                                context_entry=entry,
                                issue_text=issue,
                                signals_summary=candidate.evidence_summary or "",
                            )
                        )
                    reasoning_chain = reasoning.reasoning_chain
                symbols.append(
                    CandidateSymbol(
                        candidate_id=f"candidate:symbol:{node.node_id}",
                        symbol_node_id=node.node_id,
                        symbol_path=node.qualified_name or node.label,
                        symbol_type=node.node_type.value,
                        file_path=candidate.file_path,
                        repo_id=candidate.repo_id,
                        span=node.span,
                        signals=[
                            CandidateSignal(
                                signal_type=signal.signal_type,
                                raw_score=signal.raw_score,
                                weight=signal.weight,
                                weighted_score=signal.weighted_score,
                                evidence=signal.evidence,
                                source_refs=signal.source_refs,
                                confidence=signal.confidence,
                            )
                            for signal in candidate.signals
                        ],
                        combined_score=candidate.combined_score,
                        confidence=candidate.confidence,
                        reasoning_chain=reasoning_chain,
                    )
                )
        return symbols


def _budget_max_files(budget: JsonObject | None) -> int | None:
    if not budget:
        return None
    value = budget.get("max_files")
    if isinstance(value, int):
        return min(max(value, 1), 20)
    return None


def _signals_missing(available_signals: set[SignalType]) -> list[SignalType]:
    expected = {
        SignalType.KEYWORD,
        SignalType.EMBEDDING,
        SignalType.SARIF_PROXIMITY,
        SignalType.BLAME_HISTORY,
        SignalType.GRAPH_NEIGHBOUR,
        SignalType.SBFL,
        SignalType.MEMORY_HINT,
    }
    return sorted(expected - available_signals, key=lambda item: item.value)


def _stack_frames_resolved(issue: IssueText, candidates: list[CandidateFile]) -> bool:
    if not issue.stack_trace_frames:
        return True
    for frame in issue.stack_trace_frames:
        if not frame.file_path:
            continue
        if any(
            _path_matches(frame.file_path, candidate.file_path)
            for candidate in candidates
        ):
            return True
    return False


def _path_matches(left: str, right: str) -> bool:
    normalized = left.strip("/").replace("\\", "/")
    return (
        normalized == right or right.endswith(normalized) or normalized.endswith(right)
    )


__all__ = [
    "CandidateFile",
    "CandidateSignal",
    "CandidateSymbol",
    "ConfidenceLevel",
    "LocalisationRequest",
    "LocalisationResult",
    "LocalisationService",
    "SignalType",
]
