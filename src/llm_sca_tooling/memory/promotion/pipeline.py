"""Operational lesson promotion — requires human review approval."""

from __future__ import annotations

import uuid

from llm_sca_tooling.memory.models import OperationalLesson, ProjectMemoryRecord
from llm_sca_tooling.memory.store import MemoryStore


class UnreviewedLessonError(Exception):
    """Raised when an unreviewed lesson is submitted for promotion."""


def promote_lesson(
    lesson: OperationalLesson,
    store: MemoryStore,
    *,
    review_approved: bool = False,
) -> tuple[OperationalLesson, str | None]:
    """Promote an operational lesson. Returns (updated_lesson, promoted_to_ref)."""
    if not review_approved or lesson.review_state != "approved":
        raise UnreviewedLessonError(
            f"lesson {lesson.lesson_id!r} requires human review approval"
        )

    promoted_to_ref: str | None = None

    if lesson.target_type == "memory":
        record_id = f"pmr:{uuid.uuid4().hex[:8]}"
        pmr = ProjectMemoryRecord(
            record_id=record_id,
            repo_id=str(lesson.structured_content.get("repo_id", "unknown")),
            record_type="decision",
            content_structured=lesson.structured_content,
            source_run_id=lesson.source_run_id,
            source_event_id=lesson.source_event_id,
            owner=lesson.owner,
            review_state="approved",
            rollback_path=lesson.rollback_path,
        )
        store.put_project_record(pmr)
        promoted_to_ref = f"project_memory:{record_id}"
    elif lesson.target_type == "governance_policy":
        promoted_to_ref = "governance:requires_manifest_change_review"
    else:
        promoted_to_ref = f"{lesson.target_type}:pending"

    updated = lesson.model_copy(
        update={
            "review_state": "approved",
            "promoted_to_ref": promoted_to_ref,
        }
    )
    store.update_lesson(lesson.lesson_id, **updated.model_dump())
    return updated, promoted_to_ref
