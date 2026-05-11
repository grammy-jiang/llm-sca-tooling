"""Tests for LLMHindsightRelabeller."""

from __future__ import annotations

from llm_sca_tooling.memory.models import (
    ReviewState,
    TrajectoryOutcome,
    TrajectoryRecord,
    TrajectoryUtility,
)
from llm_sca_tooling.memory.relabelling import LLMHindsightRelabeller


def _make_trajectory() -> TrajectoryRecord:
    return TrajectoryRecord(
        trajectory_id="traj:test",
        repo_id="repo:test",
        workflow_type="bug-resolve",
        issue_class="sql-injection",
        issue_text_hash="abc123",
        graph_snapshot_id="snap:1",
        outcome=TrajectoryOutcome.UNCERTAIN,
        source_run_id="run:1",
    )


def test_llm_relabeller_attributes() -> None:
    relabeller = LLMHindsightRelabeller()
    assert relabeller.model_id == "llm-hindsight"
    assert relabeller.version == "phase17-v1"


def test_relabel_with_success_keyword() -> None:
    relabeller = LLMHindsightRelabeller()
    traj = _make_trajectory()
    label = relabeller.relabel(traj, "goal: fix resolved the bug")
    assert label.relabelled_outcome is TrajectoryOutcome.RELABELLED
    assert label.confidence == "high"
    assert label.relabelled_utility is TrajectoryUtility.HIGH


def test_relabel_with_uncertain_keyword() -> None:
    relabeller = LLMHindsightRelabeller()
    traj = _make_trajectory()
    label = relabeller.relabel(traj, "partial fix maybe works")
    assert label.relabelled_outcome is TrajectoryOutcome.UNCERTAIN
    assert label.confidence == "low"
    assert label.relabelled_utility is TrajectoryUtility.LOW


def test_relabel_default_medium_confidence() -> None:
    relabeller = LLMHindsightRelabeller()
    traj = _make_trajectory()
    label = relabeller.relabel(traj, "goal: check database queries")
    assert label.relabelled_outcome is TrajectoryOutcome.RELABELLED
    assert label.confidence == "medium"


def test_relabel_preserves_metadata() -> None:
    relabeller = LLMHindsightRelabeller()
    traj = _make_trajectory()
    goal = "fix success"
    label = relabeller.relabel(traj, goal)
    assert label.trajectory_id == "traj:test"
    assert label.original_outcome is TrajectoryOutcome.UNCERTAIN
    assert label.relabelled_goal == goal
    assert label.generator_model == "llm-hindsight"
    assert label.review_state is ReviewState.UNREVIEWED
    assert "run:1" in label.evidence_refs


def test_relabel_with_sampling_client_resolved() -> None:
    class StubSampler:
        def sample(self, prompt: str) -> str:
            return "RESOLVED"

    relabeller = LLMHindsightRelabeller(sampling_client=StubSampler())
    traj = _make_trajectory()
    label = relabeller.relabel(traj, "any goal")
    assert label.relabelled_outcome is TrajectoryOutcome.RESOLVED
    assert label.confidence == "high"


def test_relabel_with_sampling_client_no_fix() -> None:
    class StubSampler:
        def sample(self, prompt: str) -> str:
            return "NO_FIX_FOUND"

    relabeller = LLMHindsightRelabeller(sampling_client=StubSampler())
    traj = _make_trajectory()
    label = relabeller.relabel(traj, "any goal")
    assert label.relabelled_outcome is TrajectoryOutcome.NO_FIX_FOUND


def test_relabel_with_sampling_client_exception_falls_back() -> None:
    class FailingSampler:
        def sample(self, prompt: str) -> str:
            raise RuntimeError("network error")

    relabeller = LLMHindsightRelabeller(sampling_client=FailingSampler())
    traj = _make_trajectory()
    label = relabeller.relabel(traj, "resolved goal")
    assert label.relabelled_outcome is TrajectoryOutcome.RELABELLED


def test_relabeller_exported_from_package() -> None:
    from llm_sca_tooling.memory.relabelling import LLMHindsightRelabeller as Imported

    assert Imported is LLMHindsightRelabeller
