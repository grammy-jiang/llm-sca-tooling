"""Tests for FL LLM reasoning chains (FLSamplingClient and llm_chain)."""

from __future__ import annotations

from llm_sca_tooling.fl.issue import normalize_issue_text
from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    ContextFileEntry,
    SignalType,
)
from llm_sca_tooling.fl.reasoning import (
    CandidateReasoningInput,
    FLSamplingClient,
    ReasoningChainScaffold,
)
from llm_sca_tooling.schemas.enums import SnapshotConsistency
from llm_sca_tooling.storage.graph_queries import GraphSlice


def _make_candidate(file_path: str = "src/foo.py") -> CandidateFile:
    return CandidateFile(
        candidate_id=f"candidate:{file_path}",
        file_path=file_path,
        repo_id="repo:test",
        node_id=file_path,
        signals=[
            CandidateSignal(
                signal_type=SignalType.KEYWORD, raw_score=0.7, evidence="kw"
            )
        ],
        combined_score=0.7,
        confidence=ConfidenceLevel.HEURISTIC,
        snapshot_id="snap:1",
    )


def _make_context_entry(file_path: str = "src/foo.py") -> ContextFileEntry:
    slice_ = GraphSlice(
        repo_id="repo:test",
        snapshot_ids=["snap:1"],
        snapshot_consistency=SnapshotConsistency.CLEAN,
        nodes=[],
        edges=[],
    )
    return ContextFileEntry(
        candidate_file=_make_candidate(file_path),
        graph_slice=slice_,
    )


def test_fl_sampling_client_protocol() -> None:
    class MySampler:
        def sample(self, prompt: str) -> str:
            return "src/foo.py is the root cause."

    sampler = MySampler()
    assert isinstance(sampler, FLSamplingClient)


def test_build_reasoning_prompt_includes_file_path() -> None:
    scaffold = ReasoningChainScaffold()
    candidate = _make_candidate()
    entry = _make_context_entry()
    issue = normalize_issue_text("KeyError in validate_input")
    ri = CandidateReasoningInput(
        candidate_file=candidate,
        context_entry=entry,
        issue_text=issue,
        signals_summary="keyword match",
    )
    prompt = scaffold._build_reasoning_prompt(ri)
    assert "src/foo.py" in prompt
    assert "KeyError" in prompt


def test_llm_chain_with_sampler() -> None:
    class StubSampler:
        def sample(self, prompt: str) -> str:
            return "src/foo.py handles validation and is likely the root cause."

    scaffold = ReasoningChainScaffold()
    candidate = _make_candidate()
    entry = _make_context_entry()
    issue = normalize_issue_text("KeyError in validate_input")
    ri = CandidateReasoningInput(
        candidate_file=candidate,
        context_entry=entry,
        issue_text=issue,
        signals_summary="keyword match",
    )
    result = scaffold.llm_chain(ri, StubSampler())
    assert result.derivation == "llm"
    assert result.candidate_id == candidate.candidate_id
    assert result.file_path == "src/foo.py"
    assert result.reasoning_chain


def test_llm_chain_falls_back_on_sampler_error() -> None:
    class FailSampler:
        def sample(self, prompt: str) -> str:
            raise RuntimeError("timeout")

    scaffold = ReasoningChainScaffold()
    candidate = _make_candidate()
    entry = _make_context_entry()
    issue = normalize_issue_text("NullPointerException in handler")
    ri = CandidateReasoningInput(
        candidate_file=candidate,
        context_entry=entry,
        issue_text=issue,
        signals_summary="",
    )
    result = scaffold.llm_chain(ri, FailSampler())
    assert result.derivation == "llm"
    assert "sampling error" in result.reasoning_chain


def test_deterministic_chain_has_deterministic_derivation() -> None:
    scaffold = ReasoningChainScaffold()
    candidate = _make_candidate()
    entry = _make_context_entry()
    issue = normalize_issue_text("error in handler")
    ri = CandidateReasoningInput(
        candidate_file=candidate,
        context_entry=entry,
        issue_text=issue,
        signals_summary="keyword match",
    )
    result = scaffold.deterministic_chain(ri)
    assert result.derivation == "deterministic"
