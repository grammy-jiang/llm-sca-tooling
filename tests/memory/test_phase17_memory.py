from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from llm_sca_tooling.mcp_server.config import McpServerConfig
from llm_sca_tooling.mcp_server.context import McpServerContext
from llm_sca_tooling.mcp_server.tasks import TaskManager
from llm_sca_tooling.mcp_server.tool_registry import ToolRegistry
from llm_sca_tooling.mcp_server.tools import register_core_tools
from llm_sca_tooling.memory.eviction.compactor import EvictionPolicy, compact
from llm_sca_tooling.memory.models import (
    HindsightLabel,
    MemoryCompactionReport,
    MemoryOptInPolicy,
    MemoryShipGateResult,
    OperationalLesson,
    TrajectoryRecord,
)
from llm_sca_tooling.memory.policy import (
    MemoryDisabledError,
    check_memory_enabled,
    make_default_policy,
    opt_in,
)
from llm_sca_tooling.memory.promotion.pipeline import (
    UnreviewedLessonError,
    promote_lesson,
)
from llm_sca_tooling.memory.relabelling.null_relabeller import NullHindsightRelabeller
from llm_sca_tooling.memory.retrieval.coarse import retrieve_coarse
from llm_sca_tooling.memory.retrieval.fine import retrieve_fine
from llm_sca_tooling.memory.retrieval.misalignment_guard import (
    apply_misalignment_guard,
    build_coarse_hint,
)
from llm_sca_tooling.memory.ship_gate import evaluate_ship_gate, memory_weight
from llm_sca_tooling.memory.store import MemoryStore
from llm_sca_tooling.memory.write_path import validate_and_write


def _make_trajectory(
    tid: str = "t1",
    repo_id: str = "repo1",
    issue_class: str = "null_deref",
    outcome: str = "resolved",
    utility: str = "high",
    review_state: str = "approved",
    source_run_id: str = "run1",
    graph_snapshot_id: str | None = "snap1",
) -> TrajectoryRecord:
    return TrajectoryRecord(
        trajectory_id=tid,
        repo_id=repo_id,
        workflow_type="bug_resolve",
        issue_class=issue_class,
        issue_text_hash="abc123",
        fl_decisions=["src/app.py"],
        graph_node_ids=["symbol:authenticate"],
        graph_snapshot_id=graph_snapshot_id,
        outcome=outcome,
        utility=utility,
        review_state=review_state,
        source_run_id=source_run_id,
    )


def test_models_round_trip() -> None:
    policy = make_default_policy("ws1")
    assert MemoryOptInPolicy.model_validate_json(policy.model_dump_json()) == policy

    traj = _make_trajectory()
    assert TrajectoryRecord.model_validate_json(traj.model_dump_json()) == traj

    with pytest.raises(ValidationError):
        TrajectoryRecord.model_validate({"trajectory_id": "x"})

    # Outcome enum coverage
    outcomes = {
        "resolved",
        "resolved_with_risk",
        "no_fix_found",
        "rejected_by_review",
        "false_positive",
        "uncertain",
        "relabelled",
    }
    assert len(outcomes) == 7

    # record_type enum coverage
    record_types = {
        "decision",
        "constraint",
        "allowed_command",
        "component",
        "incident",
        "explicit_unknown",
        "rejected_option",
    }
    assert len(record_types) == 7

    # target_type enum coverage
    target_types = {
        "memory",
        "detector",
        "eval_regression",
        "static_analysis_rule",
        "readiness_task",
        "governance_policy",
    }
    assert len(target_types) == 6


def test_memory_policy_enforcement() -> None:
    policy = make_default_policy("ws1")
    assert not policy.enabled

    # Disabled workspace rejects memory operations
    with pytest.raises(MemoryDisabledError):
        check_memory_enabled(policy)

    # Opt-in enables memory
    enabled = opt_in(policy, actor="alice")
    assert enabled.enabled
    assert enabled.opt_in_actor == "alice"
    check_memory_enabled(enabled)

    # Per-repo override disables specific repo
    with_override = enabled.model_copy(
        update={"per_repo_overrides": {"repo_secret": False}}
    )
    with pytest.raises(MemoryDisabledError):
        check_memory_enabled(with_override, "repo_secret")
    check_memory_enabled(with_override, "repo_ok")


def test_write_path_validation() -> None:
    store = MemoryStore("ws1")
    enabled_policy = opt_in(store.policy, actor="alice")
    store.policy = enabled_policy

    # Successful write
    traj = _make_trajectory(source_run_id="run1")
    result = validate_and_write(traj, store.policy)
    assert result.written is True
    assert "opt_in_check" in result.gates_passed
    assert "secret_scan" in result.gates_passed
    assert result.review_state_set == "unreviewed"

    # Memory disabled - rejected
    disabled_policy = make_default_policy("ws1")
    result_disabled = validate_and_write(traj, disabled_policy)
    assert result_disabled.written is False
    assert any("opt_in_check" in f for f in result_disabled.gate_failures)

    # Missing source_run_id - rejected
    bad_traj = _make_trajectory(source_run_id="")
    result_bad = validate_and_write(bad_traj, store.policy)
    assert result_bad.written is False

    # Secret in string field - rejected (using pattern the scanner detects)
    secret_traj = _make_trajectory()
    secret_traj = secret_traj.model_copy(update={"issue_text_hash": "password=hunter2"})
    result_secret = validate_and_write(secret_traj, store.policy)
    assert result_secret.secret_detected is True
    assert result_secret.written is False

    # Missing graph_snapshot_id - written with contradiction diagnostic
    no_snap = _make_trajectory(graph_snapshot_id=None)
    result_no_snap = validate_and_write(no_snap, store.policy)
    assert result_no_snap.written is True
    assert result_no_snap.contradiction_detected is True

    # Forbidden snippet type - rejected
    forbidden_traj = _make_trajectory()
    forbidden_traj = forbidden_traj.model_copy(
        update={"bounded_snippet_ids": ["raw_prompt"]}
    )
    result_forbidden = validate_and_write(forbidden_traj, store.policy)
    assert result_forbidden.written is False


def test_coarse_and_fine_retrieval() -> None:
    store = MemoryStore("ws1")
    store.policy = opt_in(store.policy, actor="alice")

    # Add approved trajectories
    for i, issue_class in enumerate(["null_deref", "sql_injection", "null_deref"]):
        traj = _make_trajectory(
            tid=f"t{i}",
            issue_class=issue_class,
            outcome="resolved" if i < 2 else "no_fix_found",
        )
        store.put_trajectory(traj)

    # Coarse retrieval: matches by issue class
    active, rejected = retrieve_coarse("null deref pointer exception", "repo1", store)
    assert active
    assert all(not h.rejected for h in active)

    # Fine retrieval
    active_fine, _ = retrieve_fine("null deref in authentication", "repo1", store)
    assert isinstance(active_fine, list)


def test_misalignment_guard() -> None:
    traj = _make_trajectory(utility="low", review_state="approved")

    # High similarity + low utility - rejected
    rejected, reason = apply_misalignment_guard(traj, similarity_score=0.9)
    assert rejected is True
    assert "high_similarity_low_utility" in (reason or "")

    # Low similarity + low utility - not rejected
    ok, _ = apply_misalignment_guard(traj, similarity_score=0.5)
    assert ok is False

    # Unreviewed - rejected
    unreviewed = _make_trajectory(review_state="unreviewed")
    rej2, _ = apply_misalignment_guard(unreviewed, 0.1)
    assert rej2 is True

    # Rejected records appear in output with reason
    hint = build_coarse_hint(traj, 0.9)
    assert hint.rejected is True
    assert hint.rejection_reason is not None


def test_hindsight_relabelling() -> None:
    store = MemoryStore("ws1")
    store.policy = opt_in(store.policy, actor="alice")
    relabeller = NullHindsightRelabeller()

    original = _make_trajectory(tid="orig", outcome="no_fix_found")
    store.put_trajectory(original)

    label = relabeller.relabel(original, candidate_goal="sibling_fix")
    assert isinstance(label, HindsightLabel)
    assert label.trajectory_id == "orig"
    assert label.original_outcome == "no_fix_found"
    assert label.generator_model == "null"
    assert label.review_state == "unreviewed"

    # Relabelled record stored as NEW; original unchanged
    new_record = relabeller.create_relabelled_record(original, label, store)
    assert new_record.trajectory_id != "orig"
    assert new_record.relabelled is True
    assert new_record.review_state == "unreviewed"

    # Original unchanged
    orig_stored = store.get_trajectory("orig")
    assert orig_stored is not None
    assert orig_stored.relabelled is False


def test_eviction_compaction() -> None:
    store = MemoryStore("ws1")
    store.policy = opt_in(store.policy, actor="alice")
    policy = EvictionPolicy(
        utility_threshold_keep=0.7,
        utility_threshold_demote=0.3,
        outcome_diversity_target=2,
    )

    # Add trajectories with various utilities
    for i in range(5):
        traj = _make_trajectory(
            tid=f"t{i}",
            outcome="resolved" if i < 3 else "no_fix_found",
            utility="unknown",
        )
        store.put_trajectory(traj)

    # Dry run doesn't modify records
    report = compact("repo1", store, policy, dry_run=True)
    assert isinstance(report, MemoryCompactionReport)
    assert report.dry_run is True
    assert report.initial_count == 5

    # Live compaction
    report_live = compact("repo1", store, policy, dry_run=False)
    assert report_live.dry_run is False
    assert report_live.outcome_diversity_achieved >= 1


def test_operational_lesson_promotion() -> None:
    store = MemoryStore("ws1")
    store.policy = opt_in(store.policy, actor="alice")
    store.policy = store.policy.model_copy(
        update={"allow_operational_lesson_promotion": True}
    )

    lesson = OperationalLesson(
        lesson_id="l1",
        source_run_id="run1",
        trigger_condition="repeated_null_deref",
        lesson_type="incident",
        structured_content={"repo_id": "repo1", "key": "value"},
        target_type="memory",
        owner="alice",
        review_state="unreviewed",
    )
    store.put_lesson(lesson)

    # Unreviewed lesson - rejected
    with pytest.raises(UnreviewedLessonError):
        promote_lesson(lesson, store, review_approved=False)

    # Approved lesson - promoted to ProjectMemoryRecord
    approved_lesson = lesson.model_copy(update={"review_state": "approved"})
    store.put_lesson(approved_lesson)
    updated, ref = promote_lesson(approved_lesson, store, review_approved=True)
    assert updated.promoted_to_ref is not None
    assert "project_memory" in (ref or "")

    # Governance policy promotion - requires manifest review note
    gov_lesson = lesson.model_copy(
        update={"review_state": "approved", "target_type": "governance_policy"}
    )
    store.put_lesson(gov_lesson)
    _, gov_ref = promote_lesson(gov_lesson, store, review_approved=True)
    assert "governance" in (gov_ref or "")


def test_ship_gate() -> None:
    # Gate not met (delta < 3pp)
    result = evaluate_ship_gate("e1", pass_rate_strategy=70.0, pass_rate_baseline=68.0)
    assert isinstance(result, MemoryShipGateResult)
    assert result.gate_passed is False
    assert memory_weight(result) == 0.0

    # Gate met (delta >= 3pp)
    result2 = evaluate_ship_gate("e2", pass_rate_strategy=75.0, pass_rate_baseline=70.0)
    assert result2.gate_passed is True
    assert memory_weight(result2) == 1.0


@pytest.mark.asyncio
async def test_memory_tools_lifecycle(tmp_path) -> None:
    config = McpServerConfig(workspace_path=tmp_path, in_memory_workspace=True)
    context = await McpServerContext.create(config)
    try:
        tasks = TaskManager(tmp_path, config, context.telemetry)
        handlers = register_core_tools(ToolRegistry(), context, tasks)

        # record_trajectory — memory disabled - rejected
        rec_disabled = await handlers.record_trajectory(
            {
                "issue_text_hash": "abc",
                "outcome": "resolved",
                "source_run_id": "run1",
                "repo_id": "repo1",
            }
        )
        assert rec_disabled.status == "rejected"

        # Enable memory
        handlers._memory_store.policy = opt_in(
            handlers._memory_store.policy, actor="test"
        )

        # record_trajectory - success
        rec_ok = await handlers.record_trajectory(
            {
                "issue_text_hash": "abc",
                "outcome": "resolved",
                "source_run_id": "run1",
                "repo_id": "repo1",
                "graph_snapshot_id": "snap1",
            }
        )
        assert rec_ok.payload["write_path_result"]["written"] is True

        # retrieve_memory - coarse phase
        retrieve = await handlers.retrieve_memory(
            {"issue_text": "null deref exception", "phase": "investigate"}
        )
        assert "active_hints" in retrieve.payload
        assert retrieve.payload["weight"] == 0.0

        # memory_compact - dry run
        compact_result = await handlers.memory_compact(
            {"repo": "repo1", "dry_run": True}
        )
        assert "report" in compact_result.payload

        # memory_compact - task mode
        queued = await handlers.memory_compact(
            {"repo": "repo1", "dry_run": True, "task": True}
        )
        task_id = queued.payload["task"]["task_id"]
        for _ in range(20):
            if tasks.get(task_id, include_expired=True).status == "completed":
                break
            await asyncio.sleep(0.01)
        assert tasks.result(task_id)["result_available"] is True

        # promote_operational_lesson - unapproved
        unreviewed_result = await handlers.promote_operational_lesson(
            {
                "source_run_id": "run1",
                "target_type": "memory",
                "review_approved": False,
                "trigger_condition": "test",
                "lesson_type": "incident",
                "structured_content": {"repo_id": "repo1"},
            }
        )
        assert unreviewed_result.status == "rejected"

        # promote_operational_lesson - approved
        approved_result = await handlers.promote_operational_lesson(
            {
                "source_run_id": "run1",
                "target_type": "memory",
                "review_approved": True,
                "trigger_condition": "test",
                "lesson_type": "incident",
                "structured_content": {"repo_id": "repo1"},
            }
        )
        assert approved_result.status == "completed"
        assert approved_result.payload["promoted_to_ref"] is not None
    finally:
        await context.close()
