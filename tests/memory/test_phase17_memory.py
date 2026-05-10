from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from llm_sca_tooling.mcp_server.resources.memory import MemoryTrajectoriesResource
from llm_sca_tooling.mcp_server.tools.memory import (
    MemoryCompactTool,
    PromoteOperationalLessonTool,
    RecordTrajectoryTool,
    RetrieveMemoryTool,
)
from llm_sca_tooling.memory.eviction.compactor import MemoryCompactor
from llm_sca_tooling.memory.models import (
    LessonTargetType,
    MemoryOptInPolicy,
    ProjectMemoryRecord,
    ProjectMemoryRecordType,
    ReviewState,
    TrajectoryOutcome,
    TrajectoryRecord,
    TrajectoryUtility,
)
from llm_sca_tooling.memory.promotion.pipeline import promote_operational_lesson
from llm_sca_tooling.memory.relabelling.null_relabeller import NullHindsightRelabeller
from llm_sca_tooling.memory.retrieval.coarse import CoarseRetriever
from llm_sca_tooling.memory.retrieval.fine import FineRetriever
from llm_sca_tooling.memory.ship_gate import evaluate_memory_ship_gate
from llm_sca_tooling.memory.store import MemoryStore
from llm_sca_tooling.memory.write_path import write_trajectory
from llm_sca_tooling.storage.workspace import _now_ts, initialize_workspace


def _workspace(tmp_path: Path):
    workspace = initialize_workspace(tmp_path / "workspace")
    store = MemoryStore(workspace.conn)
    policy = MemoryOptInPolicy(
        workspace_id=store.workspace_id(),
        enabled=True,
        allow_operational_lesson_promotion=True,
        allow_hindsight_relabelling=True,
        opt_in_ts=_now_ts(),
        opt_in_actor="tester",
    )
    store.set_policy(policy)
    return workspace, store, policy


def _trajectory(
    *,
    trajectory_id: str = "traj:1",
    repo_id: str = "repo:demo",
    issue_class: str = "sql-injection",
    outcome: TrajectoryOutcome = TrajectoryOutcome.RESOLVED,
    utility: TrajectoryUtility = TrajectoryUtility.HIGH,
    review_state: ReviewState = ReviewState.APPROVED,
    graph_node_ids: list[str] | None = None,
    bounded_snippet_ids: list[str] | None = None,
) -> TrajectoryRecord:
    return TrajectoryRecord(
        trajectory_id=trajectory_id,
        repo_id=repo_id,
        workflow_type="bug-resolve",
        issue_class=issue_class,
        issue_text_hash="hash:issue",
        fl_decisions=[{"file": "app.py"}],
        graph_node_ids=graph_node_ids or ["node:app"],
        graph_snapshot_id="snap:1",
        patch_diff_hash="hash:diff",
        patch_class="predicate-guard",
        outcome=outcome,
        utility=utility,
        source_run_id="run:1",
        bounded_snippet_ids=bounded_snippet_ids or ["snippet:1"],
        review_state=review_state,
    )


def test_policy_disabled_by_default_and_enabled_requires_actor() -> None:
    policy = MemoryOptInPolicy(workspace_id="workspace:1")
    assert policy.enabled is False
    with pytest.raises(ValueError):
        MemoryOptInPolicy(workspace_id="workspace:1", enabled=True)


def test_models_round_trip_and_enum_values() -> None:
    trajectory = _trajectory()
    assert (
        TrajectoryRecord.model_validate_json(trajectory.model_dump_json()) == trajectory
    )
    assert {item.value for item in TrajectoryOutcome} == {
        "resolved",
        "resolved_with_risk",
        "no_fix_found",
        "rejected_by_review",
        "false_positive",
        "uncertain",
        "relabelled",
    }
    assert {item.value for item in ProjectMemoryRecordType} == {
        "decision",
        "constraint",
        "allowed_command",
        "component",
        "incident",
        "explicit_unknown",
        "rejected_option",
    }


def test_project_memory_rejects_prose_only_content() -> None:
    with pytest.raises(ValueError):
        ProjectMemoryRecord(
            record_id="pmem:1",
            repo_id="repo:demo",
            record_type=ProjectMemoryRecordType.DECISION,
            content_structured={"text": "do better"},
            source_run_id="run:1",
            source_event_id="event:1",
            owner="team",
            rollback_path="delete record",
        )


def test_write_path_disabled_and_secret_rejection(tmp_path: Path) -> None:
    workspace = initialize_workspace(tmp_path / "workspace")
    store = MemoryStore(workspace.conn)
    disabled = write_trajectory(
        store=store,
        policy=store.get_policy(),
        trajectory=_trajectory(review_state=ReviewState.UNREVIEWED),
    )
    assert disabled.written is False
    assert disabled.gate_failures == ["MemoryDisabled:workspace_disabled"]
    _, store, policy = _workspace(tmp_path / "enabled")
    secret = _trajectory(bounded_snippet_ids=["snippet:api_key=abc123"])
    rejected = write_trajectory(store=store, policy=policy, trajectory=secret)
    assert rejected.secret_detected is True
    assert "SecretDetected" in rejected.gate_failures


def test_write_path_contradiction_is_diagnostic_not_blocking(tmp_path: Path) -> None:
    _, store, policy = _workspace(tmp_path)
    result = write_trajectory(
        store=store,
        policy=policy,
        trajectory=_trajectory(graph_node_ids=["missing:node"]),
    )
    assert result.written is True
    assert result.contradiction_detected is True
    assert result.diagnostics[0]["code"] == "contradiction_detected"


def test_write_path_rejects_raw_trace_and_full_source_refs(tmp_path: Path) -> None:
    _, store, policy = _workspace(tmp_path)
    result = write_trajectory(
        store=store,
        policy=policy,
        trajectory=_trajectory(bounded_snippet_ids=["full_trace:trace:1"]),
    )
    assert result.written is False
    assert "forbidden_raw_memory_reference" in result.gate_failures


def test_retrieval_returns_active_and_rejected_hints(tmp_path: Path) -> None:
    _, store, _ = _workspace(tmp_path)
    store.put_trajectory(_trajectory(trajectory_id="traj:active"))
    store.put_trajectory(
        _trajectory(
            trajectory_id="traj:low",
            utility=TrajectoryUtility.LOW,
            outcome=TrajectoryOutcome.NO_FIX_FOUND,
        )
    )
    coarse, rejected = CoarseRetriever(store).retrieve(
        issue_text="sql-injection in handler", repo_id="repo:demo"
    )
    assert [hint.trajectory_id for hint in coarse] == ["traj:active"]
    assert rejected[0].rejection_reason == "high_similarity_low_utility"
    fine, fine_rejected = FineRetriever(store).retrieve(
        issue_text="unrelated", repo_id="repo:demo", graph_node_ids=["node:app"]
    )
    assert fine[0].trajectory_id == "traj:active"
    assert fine_rejected[0].misalignment_flag is True


def test_unreviewed_trajectory_is_rejected_not_active(tmp_path: Path) -> None:
    _, store, _ = _workspace(tmp_path)
    store.put_trajectory(_trajectory(review_state=ReviewState.UNREVIEWED))
    active, rejected = CoarseRetriever(store).retrieve(
        issue_text="sql-injection", repo_id="repo:demo"
    )
    assert active == []
    assert rejected[0].rejection_reason == "unreviewed"


def test_null_hindsight_relabeller_does_not_modify_original() -> None:
    original = _trajectory(outcome=TrajectoryOutcome.NO_FIX_FOUND)
    label = NullHindsightRelabeller().relabel(original, "sibling bug")
    assert label.relabelled_goal == "sibling bug"
    assert label.review_state is ReviewState.UNREVIEWED
    assert original.relabelled is False


def test_compactor_dry_run_and_live_update_utility(tmp_path: Path) -> None:
    _, store, _ = _workspace(tmp_path)
    store.put_trajectory(
        _trajectory(
            trajectory_id="traj:fail",
            outcome=TrajectoryOutcome.NO_FIX_FOUND,
            utility=TrajectoryUtility.UNKNOWN,
        )
    )
    dry = MemoryCompactor(store).compact(repo_id="repo:demo", dry_run=True)
    assert dry.demoted_count == 1
    assert store.get_trajectory("traj:fail").utility is TrajectoryUtility.UNKNOWN
    live = MemoryCompactor(store).compact(repo_id="repo:demo", dry_run=False)
    assert live.demoted_count == 1
    assert store.get_trajectory("traj:fail").utility is TrajectoryUtility.LOW


def test_operational_lesson_promotion_requires_review(tmp_path: Path) -> None:
    _, store, policy = _workspace(tmp_path)
    with pytest.raises(ValueError):
        promote_operational_lesson(
            store=store,
            policy=policy,
            repo_id="repo:demo",
            source_run_id="run:1",
            source_event_id="event:1",
            target_type=LessonTargetType.MEMORY,
            structured_content={"condition": "x", "action": "y"},
            owner="team",
            expiry_ts=None,
            rollback_path="delete record",
            review_approved=False,
        )
    lesson, promoted = promote_operational_lesson(
        store=store,
        policy=policy,
        repo_id="repo:demo",
        source_run_id="run:1",
        source_event_id="event:1",
        target_type=LessonTargetType.MEMORY,
        structured_content={"condition": "x", "action": "y"},
        owner="team",
        expiry_ts=None,
        rollback_path="delete record",
        review_approved=True,
    )
    assert lesson.review_state is ReviewState.APPROVED
    assert promoted is not None
    assert promoted.review_state is ReviewState.APPROVED


def test_mcp_tools_and_resource_lifecycle(tmp_path: Path) -> None:
    workspace, store, _ = _workspace(tmp_path)
    ctx = MagicMock()
    ctx.workspace = workspace
    ctx.workspace.graph = MagicMock()
    ctx.workspace.graph.fetch_node.return_value = object()
    ctx.authorization_context_hash = None
    record = RecordTrajectoryTool().call(
        ctx,
        {
            "repo": "repo:demo",
            "workflow_type": "bug-resolve",
            "issue_class": "sql-injection",
            "issue_text_hash": "hash:issue",
            "graph_node_ids": ["node:app"],
            "graph_snapshot_id": "snap:1",
            "outcome": "resolved",
            "source_run_id": "run:1",
        },
    )
    assert record.status == "completed"
    trajectory_id = record.payload["write_path"]["trajectory_id"]
    stored = store.get_trajectory(trajectory_id)
    store.put_trajectory(
        stored.model_copy(update={"review_state": ReviewState.APPROVED})
    )
    retrieved = RetrieveMemoryTool().call(
        ctx,
        {
            "repo": "repo:demo",
            "issue_text": "sql-injection",
            "phase": "investigate",
        },
    )
    assert retrieved.payload["hints"]
    compacted = MemoryCompactTool().call(ctx, {"repo": "repo:demo", "dry_run": True})
    assert compacted.payload["report"]["initial_count"] == 1
    promoted = PromoteOperationalLessonTool().call(
        ctx,
        {
            "repo": "repo:demo",
            "source_run_id": "run:1",
            "source_event_id": "event:1",
            "target_type": "memory",
            "structured_content": {"condition": "x", "action": "y"},
            "owner": "team",
            "rollback_path": "delete record",
            "review_approved": True,
        },
    )
    assert promoted.status == "completed"
    resource = MemoryTrajectoriesResource().read(
        ctx,
        "code-intelligence://memory/repo:demo/trajectories",
        MagicMock(authority="memory", segments=["repo:demo", "trajectories"]),
    )
    assert resource.payload["trajectory_count"] == 1
    assert resource.payload["memory_policy_status"] == "enabled"


def test_retrieve_memory_disabled_status(tmp_path: Path) -> None:
    workspace = initialize_workspace(tmp_path / "workspace")
    ctx = MagicMock()
    ctx.workspace = workspace
    result = RetrieveMemoryTool().call(
        ctx,
        {"repo": "repo:demo", "issue_text": "sql-injection", "phase": "investigate"},
    )
    assert result.status == "memory_disabled"
    assert result.payload["memory_hint_weight"] == 0.0


def test_ship_gate_weight_zero_until_delta_threshold() -> None:
    failed = evaluate_memory_ship_gate(
        eval_run_id="eval:1",
        pass_rate_strategy=0.52,
        pass_rate_baseline=0.50,
        context_budget_used=4000,
        harness_condition_id="hcs:1",
    )
    assert failed.gate_passed is False
    assert failed.memory_hint_weight == 0.0
    passed = evaluate_memory_ship_gate(
        eval_run_id="eval:2",
        pass_rate_strategy=0.54,
        pass_rate_baseline=0.50,
        context_budget_used=4000,
        harness_condition_id="hcs:1",
    )
    assert passed.gate_passed is True
    assert passed.memory_hint_weight == 1.0
