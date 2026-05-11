"""Feedback module — user ratings and re-ranking hints (Phase 16 / Gap 5)."""

from __future__ import annotations

from llm_sca_tooling.feedback.models import FeedbackRecord
from llm_sca_tooling.feedback.store import FeedbackStore

__all__ = [
    "FeedbackRecord",
    "FeedbackStore",
]
