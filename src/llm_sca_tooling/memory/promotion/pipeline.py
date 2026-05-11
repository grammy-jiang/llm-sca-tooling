"""Operational lesson promotion pipeline."""

from __future__ import annotations

import uuid

from llm_sca_tooling.memory.models import (
    LessonTargetType,
    MemoryOptInPolicy,
    OperationalLesson,
    ProjectMemoryRecord,
    ProjectMemoryRecordType,
    ReviewState,
)
from llm_sca_tooling.memory.store import MemoryStore


def promote_operational_lesson(
    *,
    store: MemoryStore,
    policy: MemoryOptInPolicy,
    repo_id: str,
    source_run_id: str,
    source_event_id: str,
    target_type: LessonTargetType,
    structured_content: dict[str, object],
    owner: str,
    expiry_ts: str | None,
    rollback_path: str,
    review_approved: bool,
    trigger_condition: str = "reviewed operational lesson",
    lesson_type: str = "operational",
) -> tuple[OperationalLesson, ProjectMemoryRecord | None]:
    if not policy.enabled or not policy.repo_enabled(repo_id):
        raise ValueError("MemoryDisabled")
    if not policy.allow_operational_lesson_promotion:
        raise ValueError("operational lesson promotion disabled")
    if policy.review_required_for_promotion and not review_approved:
        raise ValueError("review_approved is required")
    review_state = ReviewState.APPROVED if review_approved else ReviewState.UNREVIEWED
    promoted: ProjectMemoryRecord | None = None
    promoted_ref: str | None = None
    if target_type is LessonTargetType.MEMORY:
        promoted = ProjectMemoryRecord(
            record_id=f"pmem:{uuid.uuid4().hex}",
            repo_id=repo_id,
            record_type=ProjectMemoryRecordType.CONSTRAINT,
            content_structured={
                "trigger_condition": trigger_condition,
                "lesson": structured_content,
            },
            source_run_id=source_run_id,
            source_event_id=source_event_id,
            owner=owner,
            expiry_ts=expiry_ts,
            review_state=ReviewState.APPROVED,
            rollback_path=rollback_path,
        )
        store.put_project_memory(promoted)
        promoted_ref = promoted.record_id
    elif target_type is LessonTargetType.DETECTOR:
        promoted = ProjectMemoryRecord(
            record_id=f"pmem:{uuid.uuid4().hex}",
            repo_id=repo_id,
            record_type=ProjectMemoryRecordType.COMPONENT,
            content_structured={
                "trigger_condition": trigger_condition,
                "detector": structured_content,
            },
            source_run_id=source_run_id,
            source_event_id=source_event_id,
            owner=owner,
            expiry_ts=expiry_ts,
            review_state=ReviewState.APPROVED,
            rollback_path=rollback_path,
        )
        store.put_project_memory(promoted)
        promoted_ref = promoted.record_id
    elif target_type is LessonTargetType.EVAL_REGRESSION:
        promoted = ProjectMemoryRecord(
            record_id=f"pmem:{uuid.uuid4().hex}",
            repo_id=repo_id,
            record_type=ProjectMemoryRecordType.DECISION,
            content_structured={
                "trigger_condition": trigger_condition,
                "regression": structured_content,
            },
            source_run_id=source_run_id,
            source_event_id=source_event_id,
            owner=owner,
            expiry_ts=expiry_ts,
            review_state=ReviewState.APPROVED,
            rollback_path=rollback_path,
        )
        store.put_project_memory(promoted)
        promoted_ref = promoted.record_id
    elif target_type is LessonTargetType.STATIC_ANALYSIS_RULE:
        promoted = ProjectMemoryRecord(
            record_id=f"pmem:{uuid.uuid4().hex}",
            repo_id=repo_id,
            record_type=ProjectMemoryRecordType.CONSTRAINT,
            content_structured={
                "trigger_condition": trigger_condition,
                "rule": structured_content,
            },
            source_run_id=source_run_id,
            source_event_id=source_event_id,
            owner=owner,
            expiry_ts=expiry_ts,
            review_state=ReviewState.APPROVED,
            rollback_path=rollback_path,
        )
        store.put_project_memory(promoted)
        promoted_ref = promoted.record_id
    elif target_type is LessonTargetType.READINESS_TASK:
        promoted = ProjectMemoryRecord(
            record_id=f"pmem:{uuid.uuid4().hex}",
            repo_id=repo_id,
            record_type=ProjectMemoryRecordType.COMPONENT,
            content_structured={
                "trigger_condition": trigger_condition,
                "task": structured_content,
            },
            source_run_id=source_run_id,
            source_event_id=source_event_id,
            owner=owner,
            expiry_ts=expiry_ts,
            review_state=ReviewState.APPROVED,
            rollback_path=rollback_path,
        )
        store.put_project_memory(promoted)
        promoted_ref = promoted.record_id
    elif target_type is LessonTargetType.GOVERNANCE_POLICY:
        promoted = ProjectMemoryRecord(
            record_id=f"pmem:{uuid.uuid4().hex}",
            repo_id=repo_id,
            record_type=ProjectMemoryRecordType.CONSTRAINT,
            content_structured={
                "trigger_condition": trigger_condition,
                "policy": structured_content,
            },
            source_run_id=source_run_id,
            source_event_id=source_event_id,
            owner=owner,
            expiry_ts=expiry_ts,
            review_state=ReviewState.APPROVED,
            rollback_path=rollback_path,
        )
        store.put_project_memory(promoted)
        promoted_ref = promoted.record_id
    lesson = OperationalLesson(
        lesson_id=f"lesson:{uuid.uuid4().hex}",
        source_run_id=source_run_id,
        source_event_id=source_event_id,
        trigger_condition=trigger_condition,
        lesson_type=lesson_type,
        structured_content=structured_content,
        target_type=target_type,
        owner=owner,
        expiry_ts=expiry_ts,
        review_date=expiry_ts or "unscheduled",
        rollback_path=rollback_path,
        review_state=review_state,
        promoted_to_ref=promoted_ref,
    )
    store.put_operational_lesson(lesson)
    return lesson, promoted
