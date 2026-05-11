"""LLM-backed hindsight relabeller."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from llm_sca_tooling.memory.models import (
    HindsightLabel,
    ReviewState,
    TrajectoryOutcome,
    TrajectoryRecord,
    TrajectoryUtility,
)
from llm_sca_tooling.memory.relabelling.interface import HindsightRelabellerInterface

_HIGH_CONFIDENCE_KEYWORDS = ("correct", "success", "resolved", "pass", "fixed")
_MEDIUM_CONFIDENCE_KEYWORDS = ("partial", "unknown", "uncertain", "maybe")


@runtime_checkable
class LLMSamplingClient(Protocol):
    def sample(self, prompt: str) -> str: ...


class LLMHindsightRelabeller(HindsightRelabellerInterface):
    """Hindsight relabeller that uses an LLM sampling client.

    In the null-mode stub, the outcome is determined by keyword matching
    in the candidate goal.  When a real ``sampling_client`` is provided its
    ``sample(prompt)`` method is called and the response text is inspected.
    """

    model_id = "llm-hindsight"
    version = "phase17-v1"

    def __init__(self, sampling_client: LLMSamplingClient | None = None) -> None:
        self._sampling_client = sampling_client

    def relabel(
        self, trajectory: TrajectoryRecord, candidate_goal: str
    ) -> HindsightLabel:
        outcome, confidence = self._determine_outcome(trajectory, candidate_goal)
        utility = self._determine_utility(outcome)
        return HindsightLabel(
            trajectory_id=trajectory.trajectory_id,
            original_outcome=trajectory.outcome,
            relabelled_goal=candidate_goal,
            relabelled_outcome=outcome,
            relabelled_utility=utility,
            confidence=confidence,
            evidence_refs=[trajectory.source_run_id],
            generator_model=self.model_id,
            review_state=ReviewState.UNREVIEWED,
        )

    def _determine_outcome(
        self,
        trajectory: TrajectoryRecord,
        candidate_goal: str,
    ) -> tuple[TrajectoryOutcome, str]:
        if self._sampling_client is not None:
            prompt = (
                f"Trajectory outcome: {trajectory.outcome.value}\n"
                f"Candidate goal: {candidate_goal}\n"
                "Does this trajectory achieve the candidate goal? "
                "Reply: RESOLVED, RESOLVED_WITH_RISK, NO_FIX_FOUND, or UNCERTAIN."
            )
            try:
                response: str = self._sampling_client.sample(prompt)
                return self._parse_llm_response(response, trajectory)
            except Exception:
                pass
        return self._keyword_outcome(candidate_goal, trajectory)

    def _keyword_outcome(
        self,
        candidate_goal: str,
        trajectory: TrajectoryRecord,
    ) -> tuple[TrajectoryOutcome, str]:
        goal_lower = candidate_goal.lower()
        if any(kw in goal_lower for kw in _HIGH_CONFIDENCE_KEYWORDS):
            return TrajectoryOutcome.RELABELLED, "high"
        if any(kw in goal_lower for kw in _MEDIUM_CONFIDENCE_KEYWORDS):
            return TrajectoryOutcome.UNCERTAIN, "low"
        return TrajectoryOutcome.RELABELLED, "medium"

    def _parse_llm_response(
        self,
        response: str,
        trajectory: TrajectoryRecord,
    ) -> tuple[TrajectoryOutcome, str]:
        upper = response.strip().upper()
        if "RESOLVED_WITH_RISK" in upper:
            return TrajectoryOutcome.RESOLVED_WITH_RISK, "high"
        if "RESOLVED" in upper:
            return TrajectoryOutcome.RESOLVED, "high"
        if "NO_FIX_FOUND" in upper:
            return TrajectoryOutcome.NO_FIX_FOUND, "high"
        if "UNCERTAIN" in upper:
            return TrajectoryOutcome.UNCERTAIN, "low"
        return TrajectoryOutcome.RELABELLED, "medium"

    def _determine_utility(self, outcome: TrajectoryOutcome) -> TrajectoryUtility:
        if outcome in (TrajectoryOutcome.RESOLVED, TrajectoryOutcome.RELABELLED):
            return TrajectoryUtility.HIGH
        if outcome is TrajectoryOutcome.RESOLVED_WITH_RISK:
            return TrajectoryUtility.MEDIUM
        return TrajectoryUtility.LOW
