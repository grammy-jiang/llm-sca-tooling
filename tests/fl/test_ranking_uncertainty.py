from __future__ import annotations

from llm_sca_tooling.fl.issue import normalize_issue_text
from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    ContextBudget,
    ContextBundle,
    SignalType,
)
from llm_sca_tooling.fl.ranking import RankingPolicy
from llm_sca_tooling.fl.uncertainty import UncertaintyModel


def test_ranking_rewards_signal_agreement() -> None:
    one_signal = _candidate(
        "src/a.py",
        [CandidateSignal(signal_type=SignalType.KEYWORD, raw_score=0.9, evidence="kw")],
    )
    two_signals = _candidate(
        "src/b.py",
        [
            CandidateSignal(
                signal_type=SignalType.KEYWORD, raw_score=0.9, evidence="kw"
            ),
            CandidateSignal(
                signal_type=SignalType.SARIF_PROXIMITY,
                raw_score=0.9,
                evidence="sarif",
            ),
        ],
    )

    result = RankingPolicy().merge(
        [[one_signal], [two_signals]],
        available_signals={SignalType.KEYWORD, SignalType.SARIF_PROXIMITY},
    )

    assert result.ranked_files[0].file_path == "src/b.py"
    assert result.ranked_files[0].confidence == ConfidenceLevel.ANALYSER


def test_uncertainty_notes_missing_embedding_and_budget() -> None:
    issue = normalize_issue_text("KeyError in validate")
    bundle = ContextBundle(
        files=[],
        budget_used=ContextBudget(max_files=11),
        is_over_budget=True,
    )

    assessment = UncertaintyModel().evaluate(
        agreement_score=0.0,
        base_confidence=ConfidenceLevel.ANALYSER,
        issue=issue,
        context_bundle=bundle,
        signals_missing=[SignalType.EMBEDDING],
        diagnostics=[],
        stack_frames_resolved=True,
    )

    assert assessment.confidence == ConfidenceLevel.HEURISTIC
    assert "Embedding retrieval unavailable" in (assessment.uncertainty or "")
    assert "Context exceeds recommended" in (assessment.uncertainty or "")


def _candidate(
    file_path: str, signals: list[CandidateSignal], *, generated: bool = False
) -> CandidateFile:
    return CandidateFile(
        candidate_id=f"candidate:{file_path}",
        file_path=file_path,
        repo_id="repo:demo",
        node_id=file_path,
        signals=signals,
        combined_score=max(signal.raw_score for signal in signals),
        confidence=ConfidenceLevel.HEURISTIC,
        snapshot_id="snapshot:demo",
        is_generated=generated,
    )
