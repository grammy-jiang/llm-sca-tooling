"""Explainability module for LLM responses (Gap 7)."""

from __future__ import annotations

import hashlib

from pydantic import Field

from llm_sca_tooling.schemas.base import StrictBaseModel


class ExplanationRecord(StrictBaseModel):
    """Structured explanation attached to an LLM response."""

    explanation_id: str
    run_id: str | None = None
    answer_id: str | None = None
    reasoning_steps: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: str = "unknown"
    created_ts: str


class ExplanationGenerator:
    """Generates structured explanations from evidence nodes."""

    def generate(
        self,
        answer_id: str,
        evidence: list[dict[str, object]],
        run_id: str | None = None,
    ) -> ExplanationRecord:
        """Generate an ExplanationRecord from answer evidence."""
        from llm_sca_tooling.storage.workspace import _now_ts

        exp_id = "exp:" + hashlib.sha256(answer_id.encode()).hexdigest()[:16]
        steps = [
            f"Evidence node: {ev.get('evidence_type', 'unknown')} at {ev.get('file_path', 'unknown')}"
            for ev in evidence
        ]
        return ExplanationRecord(
            explanation_id=exp_id,
            run_id=run_id,
            answer_id=answer_id,
            reasoning_steps=steps,
            evidence_ids=[str(ev.get("evidence_id", "")) for ev in evidence],
            confidence="heuristic" if evidence else "unknown",
            created_ts=_now_ts(),
        )
