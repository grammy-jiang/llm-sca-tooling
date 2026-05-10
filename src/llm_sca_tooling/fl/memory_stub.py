"""Phase 9 memory-hint integration stub."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import Field

from llm_sca_tooling.fl.issue import IssueText
from llm_sca_tooling.schemas.base import StrictBaseModel


class MemoryHint(StrictBaseModel):
    hint_id: str
    issue_class: str
    fl_class: str
    suggested_files: list[str] = Field(default_factory=list)
    suggested_symbols: list[str] = Field(default_factory=list)
    utility_score: float = Field(ge=0.0, le=1.0)
    source_run_id: str


class MemoryHintResult(StrictBaseModel):
    hints_used: list[MemoryHint] = Field(default_factory=list)
    hints_rejected: list[MemoryHint] = Field(default_factory=list)
    misalignment_guard_applied: bool = True


class MemoryHintInterface(ABC):
    @abstractmethod
    def retrieve_fl_hints(
        self, issue_text: IssueText, max_hints: int
    ) -> MemoryHintResult:
        raise NotImplementedError


class MemoryHintStub(MemoryHintInterface):
    def retrieve_fl_hints(
        self, issue_text: IssueText, max_hints: int
    ) -> MemoryHintResult:
        _ = (issue_text, max_hints)
        return MemoryHintResult()
