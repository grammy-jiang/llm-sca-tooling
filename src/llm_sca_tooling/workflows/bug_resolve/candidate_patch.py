"""Candidate patch generation interface and null adapter."""

from __future__ import annotations

from typing import Protocol

from llm_sca_tooling.workflows.bug_resolve.models import (
    CandidatePatch,
    RepairContextRecord,
)


class PatchGeneratorInterface(Protocol):
    """Protocol for candidate patch generators (LLM/null/etc.)."""

    def generate(
        self, context: RepairContextRecord
    ) -> CandidatePatch:  # pragma: no cover - protocol
        ...


def _null_diff(file_path: str, candidate_index: int) -> str:
    return (
        f"--- a/{file_path}\n"
        f"+++ b/{file_path}\n"
        f"@@ -1,1 +1,1 @@\n"
        f"-# null-adapter placeholder candidate {candidate_index}\n"
        f"+# null-adapter placeholder candidate {candidate_index} (touched)\n"
    )


class NullCandidatePatchGenerator:
    """Deterministic patch generator for null-mode workflow tests."""

    def generate(self, context: RepairContextRecord) -> CandidatePatch:
        target = context.file_suspects[0] if context.file_suspects else "PLACEHOLDER"
        diff = (
            _null_diff(target, context.candidate_index) if context.file_suspects else ""
        )
        return CandidatePatch(
            run_id=context.run_id,
            candidate_index=context.candidate_index,
            diff_text=diff,
            diff_format="unified",
            changed_files=[target] if context.file_suspects else [],
            changed_symbol_ids=[],
            generation_method="null-adapter",
            generator_model=None,
            reasoning_chain=(
                "Null adapter: placeholder change for end-to-end pipeline tests."
            ),
            certificate_ref=None,
            precondition_draft_ref=None,
            postcondition_draft_ref=None,
            confidence=0.5 if context.file_suspects else 0.0,
            provenance={
                "snapshot_id": context.snapshot_id,
                "tokens_estimate": context.context_tokens_estimate,
            },
        )


def is_valid_unified_diff(diff_text: str) -> bool:
    """Lightweight validation that a diff looks like a unified diff."""
    if not diff_text:
        return False
    has_minus = any(line.startswith("--- ") for line in diff_text.splitlines())
    has_plus = any(line.startswith("+++ ") for line in diff_text.splitlines())
    has_hunk = any(line.startswith("@@") for line in diff_text.splitlines())
    return has_minus and has_plus and has_hunk


__all__ = [
    "NullCandidatePatchGenerator",
    "PatchGeneratorInterface",
    "is_valid_unified_diff",
]
