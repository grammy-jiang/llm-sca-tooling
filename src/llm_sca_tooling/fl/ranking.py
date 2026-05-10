"""Multi-signal ranking policy for Phase 9 fault localisation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    SignalType,
)

DEFAULT_SIGNAL_WEIGHTS: dict[SignalType, float] = {
    SignalType.KEYWORD: 0.25,
    SignalType.EMBEDDING: 0.30,
    SignalType.SARIF_PROXIMITY: 0.20,
    SignalType.BLAME_HISTORY: 0.10,
    SignalType.GRAPH_NEIGHBOUR: 0.10,
    SignalType.SBFL: 0.05,
    SignalType.MEMORY_HINT: 0.00,
}


@dataclass(frozen=True)
class RankingResult:
    ranked_files: list[CandidateFile]
    agreement_score: float
    signals_used: list[SignalType]
    signals_missing: list[SignalType]


class RankingPolicy:
    def __init__(
        self,
        weights: dict[SignalType, float] | None = None,
        *,
        minimum_threshold: float = 0.05,
    ) -> None:
        self.weights = weights or DEFAULT_SIGNAL_WEIGHTS
        self.minimum_threshold = minimum_threshold

    def merge(
        self,
        candidate_groups: list[list[CandidateFile]],
        *,
        available_signals: set[SignalType],
        max_files: int | None = None,
    ) -> RankingResult:
        grouped: dict[tuple[str, str], list[CandidateFile]] = defaultdict(list)
        for group in candidate_groups:
            for candidate in group:
                grouped[(candidate.repo_id, candidate.file_path)].append(candidate)
        ranked: list[CandidateFile] = []
        for items in grouped.values():
            merged = self._merge_file(items, available_signals)
            if merged.combined_score >= self.minimum_threshold:
                ranked.append(merged)
        ranked.sort(key=_sort_key, reverse=True)
        if max_files is not None:
            ranked = ranked[:max_files]
        used = sorted(
            {
                signal.signal_type
                for candidate in ranked
                for signal in candidate.signals
            },
            key=lambda item: item.value,
        )
        missing = sorted(available_signals - set(used), key=lambda item: item.value)
        agreement = agreement_score(ranked, available_signals)
        return RankingResult(
            ranked_files=ranked,
            agreement_score=agreement,
            signals_used=used,
            signals_missing=missing,
        )

    def _merge_file(
        self, candidates: list[CandidateFile], available_signals: set[SignalType]
    ) -> CandidateFile:
        signals: list[CandidateSignal] = []
        best_by_type: dict[SignalType, CandidateSignal] = {}
        for candidate in candidates:
            for signal in candidate.signals:
                existing = best_by_type.get(signal.signal_type)
                if existing is None or signal.raw_score > existing.raw_score:
                    best_by_type[signal.signal_type] = signal
        denominator = sum(
            self.weights.get(signal_type, 0.0)
            for signal_type in available_signals
            if self.weights.get(signal_type, 0.0) > 0.0
        )
        if denominator == 0.0:
            denominator = 1.0
        total = 0.0
        for signal_type, signal in best_by_type.items():
            weight = self.weights.get(signal_type, 0.0)
            total += signal.raw_score * weight
            signals.append(signal.with_weight(weight))
        combined_score = min(1.0, total / denominator)
        agreement = _candidate_agreement(signals, available_signals)
        confidence = (
            ConfidenceLevel.ANALYSER if agreement >= 0.6 else ConfidenceLevel.HEURISTIC
        )
        seed = candidates[0]
        return seed.model_copy(
            update={
                "signals": sorted(signals, key=lambda item: item.signal_type.value),
                "combined_score": combined_score,
                "confidence": confidence,
                "evidence_summary": "; ".join(
                    signal.evidence for signal in signals[:4]
                ),
                "is_generated": any(candidate.is_generated for candidate in candidates),
            }
        )


def agreement_score(
    candidates: list[CandidateFile], available_signals: set[SignalType]
) -> float:
    if not candidates or not available_signals:
        return 0.0
    top = candidates[0]
    return _candidate_agreement(top.signals, available_signals)


def _candidate_agreement(
    signals: list[CandidateSignal], available_signals: set[SignalType]
) -> float:
    if not available_signals:
        return 0.0
    agreeing = {
        signal.signal_type
        for signal in signals
        if signal.raw_score > 0.3 and signal.signal_type in available_signals
    }
    return len(agreeing) / len(available_signals)


def _sort_key(candidate: CandidateFile) -> tuple[float, int, float, bool, str]:
    signal_types = {signal.signal_type for signal in candidate.signals}
    static_score = sum(
        signal.raw_score
        for signal in candidate.signals
        if signal.signal_type
        in {SignalType.SARIF_PROXIMITY, SignalType.GRAPH_NEIGHBOUR}
    )
    return (
        candidate.combined_score,
        len(signal_types),
        static_score,
        not candidate.is_generated,
        candidate.file_path,
    )
