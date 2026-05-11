"""Fault-localisation ranking policy."""

from __future__ import annotations

from collections import defaultdict

from llm_sca_tooling.fl.models import (
    CandidateFile,
    CandidateSignal,
    ConfidenceLevel,
    SignalType,
    candidate_id,
)

__all__ = ["DEFAULT_SIGNAL_WEIGHTS", "RankingPolicy", "agreement_score"]

DEFAULT_SIGNAL_WEIGHTS: dict[SignalType, float] = {
    SignalType.keyword: 0.25,
    SignalType.embedding: 0.30,
    SignalType.sarif_proximity: 0.20,
    SignalType.blame_history: 0.10,
    SignalType.graph_neighbour: 0.10,
    SignalType.sbfl: 0.05,
    SignalType.memory_hint: 0.00,
}


class RankingPolicy:
    def __init__(
        self,
        weights: dict[SignalType, float] | None = None,
        minimum_threshold: float = 0.05,
    ) -> None:
        self.weights = weights or DEFAULT_SIGNAL_WEIGHTS
        self.minimum_threshold = minimum_threshold

    def merge(
        self, candidate_lists: list[list[CandidateFile]], *, max_files: int = 8
    ) -> list[CandidateFile]:
        grouped: dict[tuple[str, str], list[CandidateFile]] = defaultdict(list)
        for candidates in candidate_lists:
            for candidate in candidates:
                grouped[(candidate.repo_id, candidate.file_path)].append(candidate)
        merged = [self._merge_group(key, group) for key, group in grouped.items()]
        merged = [
            candidate
            for candidate in merged
            if candidate.combined_score >= self.minimum_threshold
        ]
        return sorted(
            merged,
            key=lambda c: (
                c.is_generated,
                -len({s.signal_type for s in c.signals}),
                -c.combined_score,
            ),
        )[:max_files]

    def _merge_group(
        self, key: tuple[str, str], group: list[CandidateFile]
    ) -> CandidateFile:
        repo_id, file_path = key
        signals = [signal for candidate in group for signal in candidate.signals]
        available = {signal.signal_type for signal in signals}
        weight_sum = (
            sum(self.weights.get(signal_type, 0.0) for signal_type in available) or 1.0
        )
        score = (
            sum(
                signal.raw_score * self.weights.get(signal.signal_type, 0.0)
                for signal in signals
            )
            / weight_sum
        )
        confidence = (
            ConfidenceLevel.analyser
            if agreement_score(signals) >= 0.6
            else ConfidenceLevel.heuristic
        )
        best = max(group, key=lambda candidate: candidate.combined_score)
        return CandidateFile(
            candidate_id=candidate_id(repo_id, file_path, "ranked"),
            file_path=file_path,
            repo_id=repo_id,
            node_id=best.node_id,
            signals=[
                signal.model_copy(
                    update={
                        "weight": self.weights.get(signal.signal_type, 0.0),
                        "weighted_score": signal.raw_score
                        * self.weights.get(signal.signal_type, 0.0),
                    }
                )
                for signal in signals
            ],
            combined_score=min(score, 1.0),
            confidence=confidence,
            evidence_summary="; ".join(signal.evidence for signal in signals),
            snapshot_id=best.snapshot_id,
            is_generated=any(candidate.is_generated for candidate in group),
        )


def agreement_score(signals: list[CandidateSignal]) -> float:
    available = {signal.signal_type for signal in signals if signal.weight > 0}
    if not available:
        return 0.0
    agreeing = {signal.signal_type for signal in signals if signal.raw_score > 0.3}
    return len(agreeing) / len(available)
