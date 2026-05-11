"""Patch generator interface and null adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from llm_sca_tooling.sast_repair.models import (
    ClassificationConfidence,
    GenerationMethod,
    RepairContext,
    SASTPatch,
)


class PatchGeneratorInterface(ABC):
    """Abstract LLM boundary for SAST patch generation."""

    model_id: str
    version: str

    @abstractmethod
    def generate(self, context: RepairContext) -> SASTPatch: ...


class NullPatchGenerator(PatchGeneratorInterface):
    """Deterministic null adapter used for pipeline smoke tests."""

    def __init__(
        self,
        *,
        model_id: str = "null-adapter",
        version: str = "0.1.0",
    ) -> None:
        self.model_id = model_id
        self.version = version

    def generate(self, context: RepairContext) -> SASTPatch:
        provenance = {
            "context_tokens": context.context_tokens_estimate,
            "examples_included": len(context.predicate_examples_ref),
            "model_id": self.model_id,
            "version": self.version,
        }
        return SASTPatch(
            alert_id=context.alert_id,
            diff_text="",
            diff_format="unified",
            changed_files=[],
            generator_model=self.model_id,
            generation_method=GenerationMethod.NULL_REPAIR,
            confidence=ClassificationConfidence.UNKNOWN,
            certificate_text=None,
            reasoning_chain=["null-adapter: no patch synthesised"],
            dryrun_prediction_ref=None,
            provenance=provenance,
        )


class SamplingPatchGenerator(PatchGeneratorInterface):
    """MCP-Sampling-backed SAST patch generator.

    Falls back to :class:`NullPatchGenerator` when the sampling client is
    unavailable or the response cannot be parsed as a unified diff.
    """

    def __init__(
        self,
        sampling_client: Any,
        *,
        model_id: str = "llm-sampling",
        version: str = "0.1.0",
        max_tokens: int = 1024,
    ) -> None:
        self._client = sampling_client
        self.model_id = model_id
        self.version = version
        self._max_tokens = max_tokens
        self._fallback = NullPatchGenerator(model_id="null-adapter", version=version)

    def generate(self, context: RepairContext) -> SASTPatch:
        if self._client is None or not getattr(self._client, "available", False):
            return self._fallback.generate(context)
        prompt = self._build_prompt(context)
        try:
            response = self._client.create_message(
                prompt=prompt, max_tokens=self._max_tokens
            )
            content = str(response.get("content", "")).strip()
            diff_text = _extract_diff(content)
            if not _is_valid_diff(diff_text):
                return self._fallback.generate(context)
            changed = _changed_files_from_diff(diff_text)
            provenance: dict[str, Any] = {
                "context_tokens": context.context_tokens_estimate,
                "examples_included": len(context.predicate_examples_ref),
                "model_id": self.model_id,
                "version": self.version,
            }
            return SASTPatch(
                alert_id=context.alert_id,
                diff_text=diff_text,
                diff_format="unified",
                changed_files=changed,
                generator_model=self.model_id,
                generation_method=GenerationMethod.PREDICATE_REPAIR,
                confidence=ClassificationConfidence.HEURISTIC,
                certificate_text=None,
                reasoning_chain=["Patch generated via MCP Sampling from SAST context."],
                dryrun_prediction_ref=None,
                provenance=provenance,
            )
        except Exception:
            return self._fallback.generate(context)

    def _build_prompt(self, context: RepairContext) -> str:
        examples = "\n".join(f"  - {ref}" for ref in context.predicate_examples_ref[:3])
        snippets = (
            "\n".join(
                f"  - {ref}"
                for ref in context.bounded_snippet_refs[:3]
                if hasattr(context, "bounded_snippet_refs")
            )
            if hasattr(context, "bounded_snippet_refs")
            else ""
        )
        return (
            "You are an expert security engineer. Generate a minimal unified diff "
            "to fix the SAST alert described below.\n\n"
            f"Alert ID: {context.alert_id}\n"
            f"Explanation: {context.alert_explanation}\n"
            f"File: {context.file_path or 'unknown'}\n"
            f"Predicate examples:\n{examples or '  (none)'}\n"
            f"Bounded snippets:\n{snippets or '  (none)'}\n\n"
            "Respond with ONLY the unified diff (starting with --- and +++).\n"
        )


def _extract_diff(content: str) -> str:
    lines = content.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("--- "):
            start = i
            break
    if start is None:
        return content
    return "\n".join(lines[start:])


def _is_valid_diff(diff_text: str) -> bool:
    if not diff_text:
        return False
    has_minus = any(line.startswith("--- ") for line in diff_text.splitlines())
    has_plus = any(line.startswith("+++ ") for line in diff_text.splitlines())
    has_hunk = any(line.startswith("@@") for line in diff_text.splitlines())
    return has_minus and has_plus and has_hunk


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
) -> SamplingPatchGenerator | NullPatchGenerator:
    """Factory: returns SamplingPatchGenerator when a client is provided."""
    if sampling_client is not None:
        return SamplingPatchGenerator(sampling_client)
    return NullPatchGenerator()


__all__ = [
    "NullPatchGenerator",
    "PatchGeneratorInterface",
    "SamplingPatchGenerator",
    "create_patch_generator",
]
