"""Tests for all 6 promotion pipeline target types."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.memory.models import (
    LessonTargetType,
    MemoryOptInPolicy,
    ProjectMemoryRecordType,
)
from llm_sca_tooling.memory.promotion.pipeline import promote_operational_lesson
from llm_sca_tooling.memory.store import MemoryStore
from llm_sca_tooling.storage.workspace import initialize_workspace


def _make_store(tmp_path: Path) -> tuple[MemoryStore, MemoryOptInPolicy]:
    workspace = initialize_workspace(tmp_path / "ws")
    store = MemoryStore(workspace.conn)
    policy = MemoryOptInPolicy(
        workspace_id=store.workspace_id(),
        enabled=True,
        allow_operational_lesson_promotion=True,
        opt_in_ts="2024-01-01T00:00:00Z",
        opt_in_actor="test-agent",
    )
    return store, policy


def _promote(
    store: MemoryStore,
    policy: MemoryOptInPolicy,
    target_type: LessonTargetType,
    content: dict,
):
    return promote_operational_lesson(
        store=store,
        policy=policy,
        repo_id="repo:demo",
        source_run_id="run:1",
        source_event_id="event:1",
        target_type=target_type,
        structured_content=content,
        owner="team",
        expiry_ts=None,
        rollback_path="delete record",
        review_approved=True,
    )


def test_promote_memory_target(tmp_path: Path) -> None:
    store, policy = _make_store(tmp_path)
    lesson, promoted = _promote(
        store, policy, LessonTargetType.MEMORY, {"condition": "x", "action": "y"}
    )
    assert promoted is not None
    assert promoted.record_type is ProjectMemoryRecordType.CONSTRAINT
    assert "trigger_condition" in promoted.content_structured
    assert "lesson" in promoted.content_structured
    assert lesson.promoted_to_ref == promoted.record_id


def test_promote_detector_target(tmp_path: Path) -> None:
    store, policy = _make_store(tmp_path)
    lesson, promoted = _promote(
        store,
        policy,
        LessonTargetType.DETECTOR,
        {"condition": "sql", "action": "add_check"},
    )
    assert promoted is not None
    assert promoted.record_type is ProjectMemoryRecordType.COMPONENT
    assert "detector" in promoted.content_structured
    assert "trigger_condition" in promoted.content_structured


def test_promote_eval_regression_target(tmp_path: Path) -> None:
    store, policy = _make_store(tmp_path)
    lesson, promoted = _promote(
        store,
        policy,
        LessonTargetType.EVAL_REGRESSION,
        {"suite_id": "t1", "threshold": 0.8},
    )
    assert promoted is not None
    assert promoted.record_type is ProjectMemoryRecordType.DECISION
    assert "regression" in promoted.content_structured


def test_promote_static_analysis_rule_target(tmp_path: Path) -> None:
    store, policy = _make_store(tmp_path)
    lesson, promoted = _promote(
        store,
        policy,
        LessonTargetType.STATIC_ANALYSIS_RULE,
        {"rule_id": "S9999", "pattern": ".*"},
    )
    assert promoted is not None
    assert promoted.record_type is ProjectMemoryRecordType.CONSTRAINT
    assert "rule" in promoted.content_structured


def test_promote_readiness_task_target(tmp_path: Path) -> None:
    store, policy = _make_store(tmp_path)
    lesson, promoted = _promote(
        store,
        policy,
        LessonTargetType.READINESS_TASK,
        {"task_id": "R1", "description": "run checks"},
    )
    assert promoted is not None
    assert promoted.record_type is ProjectMemoryRecordType.COMPONENT
    assert "task" in promoted.content_structured


def test_promote_governance_policy_target(tmp_path: Path) -> None:
    store, policy = _make_store(tmp_path)
    lesson, promoted = _promote(
        store,
        policy,
        LessonTargetType.GOVERNANCE_POLICY,
        {"policy_id": "GP1", "rule": "never skip review"},
    )
    assert promoted is not None
    assert promoted.record_type is ProjectMemoryRecordType.CONSTRAINT
    assert "policy" in promoted.content_structured


def test_all_promotions_store_lesson_with_ref(tmp_path: Path) -> None:
    store, policy = _make_store(tmp_path)
    for target_type in LessonTargetType:
        content = {"condition": "test", "action": "check", "detail": str(target_type)}
        lesson, promoted = _promote(store, policy, target_type, content)
        assert lesson.promoted_to_ref is not None
        assert promoted is not None
        assert lesson.promoted_to_ref == promoted.record_id
