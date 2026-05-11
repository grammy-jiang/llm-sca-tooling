"""Candidate patch generation interface and null adapter."""

from __future__ import annotations

from typing import Any, Protocol

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


class SamplingCandidatePatchGenerator:
    """MCP-Sampling-backed candidate patch generator.

    Falls back to :class:`NullCandidatePatchGenerator` when the sampling
    client is unavailable or the response cannot be parsed as a unified diff.
    """

    def __init__(self, sampling_client: Any, *, max_tokens: int = 2048) -> None:
        self._client = sampling_client
        self._max_tokens = max_tokens
        self._fallback = NullCandidatePatchGenerator()

    def generate(self, context: RepairContextRecord) -> CandidatePatch:
        if self._client is None or not getattr(self._client, "available", False):
            return self._fallback.generate(context)
        prompt = self._build_prompt(context)
        try:
            response = self._client.create_message(
                prompt=prompt, max_tokens=self._max_tokens
            )
            content = str(response.get("content", "")).strip()
            if not content or not is_valid_unified_diff(content):
                return self._fallback.generate(context)
            diff_text = _extract_diff(content)
            if not is_valid_unified_diff(diff_text):
                return self._fallback.generate(context)
            changed = _changed_files_from_diff(diff_text)
            return CandidatePatch(
                run_id=context.run_id,
                candidate_index=context.candidate_index,
                diff_text=diff_text,
                diff_format="unified",
                changed_files=changed,
                changed_symbol_ids=[],
                generation_method="sampling",
                generator_model="llm-sampling",
                reasoning_chain="Patch generated via MCP Sampling from issue context.",
                certificate_ref=None,
                precondition_draft_ref=None,
                postcondition_draft_ref=None,
                confidence=0.7,
                provenance={
                    "snapshot_id": context.snapshot_id,
                    "tokens_estimate": context.context_tokens_estimate,
                    "generator": "SamplingCandidatePatchGenerator",
                },
            )
        except Exception:
            return self._fallback.generate(context)

    def _build_prompt(self, context: RepairContextRecord) -> str:
        suspects = "\n".join(f"  - {f}" for f in context.file_suspects[:3])
        slices = "\n".join(f"  - {s}" for s in context.graph_slices_ref[:3])
        return (
            "You are an expert software engineer. Generate a minimal unified diff "
            "to fix the issue described below.\n\n"
            f"Suspect files:\n{suspects or '  (none)'}\n\n"
            f"Graph slice refs:\n{slices or '  (none)'}\n\n"
            "Respond with ONLY the unified diff (starting with --- and +++).\n"
        )


def _extract_diff(content: str) -> str:
    """Extract unified diff block from LLM response."""
    lines = content.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("--- "):
            start = i
            break
    if start is None:
        return content
    return "\n".join(lines[start:])


def _changed_files_from_diff(diff_text: str) -> list[str]:
    files = []
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            if path and path != "/dev/null":
                files.append(path)
    return list(dict.fromkeys(files))


def create_patch_generator(
    sampling_client: Any = None,
) -> SamplingCandidatePatchGenerator | NullCandidatePatchGenerator:
    """Factory: returns SamplingCandidatePatchGenerator when a client is provided."""
    if sampling_client is not None:
        return SamplingCandidatePatchGenerator(sampling_client)
    return NullCandidatePatchGenerator()


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
    "SamplingCandidatePatchGenerator",
    "create_patch_generator",
    "is_valid_unified_diff",
]
