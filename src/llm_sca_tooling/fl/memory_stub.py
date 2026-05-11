"""Phase 9 memory hint stub."""

from __future__ import annotations

from pydantic import Field

from llm_sca_tooling.fl.issue import IssueText
from llm_sca_tooling.fl.models import StrictFlModel

__all__ = ["MemoryHint", "MemoryHintResult", "MemoryHintStub"]


class MemoryHint(StrictFlModel):
    hint_id: str
    issue_class: str
    fl_class: str
    suggested_files: list[str] = Field(default_factory=list)
    suggested_symbols: list[str] = Field(default_factory=list)
    utility_score: float = 0.0
    source_run_id: str


class MemoryHintResult(StrictFlModel):
    hints_used: list[MemoryHint] = Field(default_factory=list)
    hints_rejected: list[MemoryHint] = Field(default_factory=list)
    misalignment_guard_applied: bool = True


class MemoryHintStub:
    weight = 0.0

    def retrieve_fl_hints(
        self, issue_text: IssueText, max_hints: int
    ) -> MemoryHintResult:
        del issue_text, max_hints
        return MemoryHintResult()
