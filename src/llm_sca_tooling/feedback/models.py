"""Feedback record schema (Phase 16 / Gap 5)."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.schemas.base import StrictBaseModel


class FeedbackRecord(StrictBaseModel):
    """A single piece of user feedback attached to an LLM answer."""

    feedback_id: str
    run_id: str | None = None
    question: str
    answer_id: str | None = None
    rating: int = Field(ge=1, le=5)
    comment: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_ts: str
