"""Hindsight relabeller interface and LLM-boundary implementation (phase 17 §9).

Spec rules:
- `HindsightRelabellerInterface`: relabel(trajectory, candidate_goal) ->
  HindsightLabel, plus model_id and version attributes.
- LLM relabelling output is stored as a labelled hypothesis, not a fact:
  review_state stays "unreviewed"; the original trajectory is never modified.
- Relabelling requires `allow_hindsight_relabelling: true` in the memory policy.
"""

from __future__ import annotations

import json

import pytest

from llm_sca_tooling.memory.models import (
    MemoryOptInPolicy,
    TrajectoryRecord,
)
from llm_sca_tooling.memory.relabelling import (
    HindsightRelabellerInterface,
    LLMHindsightRelabeller,
    NullHindsightRelabeller,
    RelabellingNotAllowedError,
    relabel_and_store,
)
from llm_sca_tooling.memory.store import MemoryStore


def _trajectory(outcome: str = "no_fix_found") -> TrajectoryRecord:
    return TrajectoryRecord(
        trajectory_id="traj:0001",
        repo_id="repo:test",
        workflow_type="bug_resolve",
        issue_class="null-deref",
        issue_text_hash="hash:fix-bug-a",
        outcome=outcome,
        utility="low",
        source_run_id="run:0001",
    )


def _policy(*, allow: bool) -> MemoryOptInPolicy:
    return MemoryOptInPolicy(
        workspace_id="ws:test",
        enabled=True,
        allow_hindsight_relabelling=allow,
    )


def test_both_relabellers_satisfy_interface() -> None:
    llm = LLMHindsightRelabeller(complete=lambda prompt: "{}", model_id="test-model")
    assert isinstance(NullHindsightRelabeller(), HindsightRelabellerInterface)
    assert isinstance(llm, HindsightRelabellerInterface)
    assert llm.model_id == "test-model"
    assert llm.version


def test_llm_relabeller_parses_structured_response() -> None:
    def fake_complete(prompt: str) -> str:
        assert "traj:0001" in prompt
        assert "sibling fix B" in prompt
        return json.dumps(
            {
                "relabelled_outcome": "resolved",
                "relabelled_utility": "high",
                "confidence": "medium",
                "evidence_refs": ["patch:traj:0001/0"],
            }
        )

    relabeller = LLMHindsightRelabeller(complete=fake_complete, model_id="m1")
    label = relabeller.relabel(_trajectory(), candidate_goal="sibling fix B")

    assert label.trajectory_id == "traj:0001"
    assert label.original_outcome == "no_fix_found"
    assert label.relabelled_goal == "sibling fix B"
    assert label.relabelled_outcome == "resolved"
    assert label.relabelled_utility == "high"
    assert label.confidence == "medium"
    assert label.evidence_refs == ["patch:traj:0001/0"]
    assert label.generator_model == "m1"
    # Hypothesis, not fact.
    assert label.review_state == "unreviewed"


def test_llm_relabeller_malformed_output_falls_back_safely() -> None:
    relabeller = LLMHindsightRelabeller(
        complete=lambda prompt: "not json at all", model_id="m1"
    )
    label = relabeller.relabel(_trajectory(), candidate_goal="goal B")

    # No upgrade without parseable evidence: outcome unchanged, confidence unknown.
    assert label.relabelled_outcome == "no_fix_found"
    assert label.confidence == "unknown"
    assert label.review_state == "unreviewed"


def test_llm_relabeller_rejects_invalid_enum_values() -> None:
    relabeller = LLMHindsightRelabeller(
        complete=lambda prompt: json.dumps(
            {"relabelled_outcome": "totally_fixed_trust_me", "confidence": "absolute"}
        ),
        model_id="m1",
    )
    label = relabeller.relabel(_trajectory(), candidate_goal="goal B")
    assert label.relabelled_outcome == "no_fix_found"
    assert label.confidence == "unknown"


def test_relabel_and_store_requires_policy_opt_in() -> None:
    store = MemoryStore()
    relabeller = NullHindsightRelabeller()
    with pytest.raises(RelabellingNotAllowedError):
        relabel_and_store(
            relabeller,
            _trajectory(),
            candidate_goal="goal B",
            store=store,
            policy=_policy(allow=False),
        )


def test_relabel_and_store_keeps_original_and_stores_hypothesis() -> None:
    store = MemoryStore()
    original = _trajectory()
    store.put_trajectory(original)

    relabeller = LLMHindsightRelabeller(
        complete=lambda prompt: json.dumps(
            {"relabelled_outcome": "resolved", "relabelled_utility": "medium"}
        ),
        model_id="m1",
    )
    new_record = relabel_and_store(
        relabeller,
        original,
        candidate_goal="goal B",
        store=store,
        policy=_policy(allow=True),
    )

    assert new_record.relabelled is True
    assert new_record.review_state == "unreviewed"
    assert new_record.trajectory_id != original.trajectory_id
    stored_original = store.get_trajectory(original.trajectory_id)
    assert stored_original is not None
    assert stored_original.relabelled is False
    assert stored_original.outcome == "no_fix_found"
