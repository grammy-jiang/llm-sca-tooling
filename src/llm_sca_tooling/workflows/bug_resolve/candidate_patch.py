"""Candidate patch generation and null adapter."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

from llm_sca_tooling.workflows.bug_resolve.models import (
    CandidatePatch,
    RepairContextRecord,
)

if TYPE_CHECKING:
    from llm_sca_tooling.mcp_server.sampling import SamplingClient


class PatchGeneratorInterface(ABC):
    model_id: str
    version: str

    @abstractmethod
    def generate(self, context: RepairContextRecord) -> CandidatePatch:
        raise NotImplementedError


class NullPatchGenerator(PatchGeneratorInterface):
    model_id = "phase13-null"
    version = "1"

    def generate(self, context: RepairContextRecord) -> CandidatePatch:
        primary = context.file_suspects[0] if context.file_suspects else "src/main.py"
        diff = (
            f"diff --git a/{primary} b/{primary}\n"
            f"--- a/{primary}\n+++ b/{primary}\n"
            "@@ -1 +1 @@\n-old\n+fixed\n"
        )
        return CandidatePatch(
            run_id=context.run_id,
            candidate_index=context.candidate_index,
            diff_text=diff,
            changed_files=[primary],
            changed_symbol_ids=[f"symbol:{primary}:1"],
            generation_method="null_repair",
            generator_model=self.model_id,
            reasoning_chain=["null-mode: deterministic no-op repair"],
            confidence="unknown",
            provenance={"version": self.version},
        )


class SamplingPatchGenerator(PatchGeneratorInterface):
    """Patch generator that delegates LLM generation to the MCP Sampling client.

    Falls back to ``NullPatchGenerator`` when sampling is not available or
    when the sampling response is empty.
    """

    model_id = "sampling-patch-gen"
    version = "1"

    def __init__(self, sampling_client: SamplingClient) -> None:
        self._sampling = sampling_client
        self._null = NullPatchGenerator()

    def generate(self, context: RepairContextRecord) -> CandidatePatch:
        """Synchronously dispatch to sampling (or fall back)."""
        import asyncio  # noqa: PLC0415

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return self._null.generate(context)
            return loop.run_until_complete(self.generate_async(context))
        except Exception:  # noqa: BLE001
            return self._null.generate(context)

    async def generate_async(self, context: RepairContextRecord) -> CandidatePatch:
        """Async patch generation via MCP Sampling."""
        from llm_sca_tooling.mcp_server.sampling import SamplingRequest  # noqa: PLC0415

        if not self._sampling.is_supported:
            return self._null.generate(context)

        suspects = (
            ", ".join(context.file_suspects) if context.file_suspects else "unknown"
        )
        issue_text = (
            context.issue_text[:500]
            if hasattr(context, "issue_text")
            else "No description"
        )
        prompt = (
            f"Generate a minimal unified diff to fix the reported bug.\n\n"
            f"Run ID: {context.run_id}\n"
            f"Issue: {issue_text}\n"
            f"Suspected files: {suspects}\n\n"
            "Respond with only the unified diff text, no explanation."
        )
        request = SamplingRequest(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=(
                "You are a precise bug-fixing assistant"
                " that produces minimal unified diffs."
            ),
            max_tokens=2048,
        )
        response = await self._sampling.create_message(request)
        if not response.via_sampling or not response.content.strip():
            return self._null.generate(context)

        primary = context.file_suspects[0] if context.file_suspects else "src/main.py"
        return CandidatePatch(
            run_id=context.run_id,
            candidate_index=context.candidate_index,
            diff_text=response.content,
            changed_files=[primary],
            changed_symbol_ids=[f"symbol:{primary}:1"],
            generation_method="sampling_repair",
            generator_model=self.model_id,
            reasoning_chain=["sampling-mode"],
            confidence="medium",
            provenance={"version": self.version, "model": response.model or "unknown"},
        )


_PATCH_PROMPT = """\
You are generating a candidate repair patch from typed evidence. Produce a
minimal unified diff for the suspect files; do not invent files that are not
listed.

run_id: {run_id}
language: {language}
file_suspects: {suspects}
sarif_alerts_in_scope: {alert_count}

Respond with a single JSON object and nothing else:
{{"diff_text": "<unified diff>",
 "changed_files": ["<files from file_suspects this diff touches>"],
 "reasoning": ["<short reasoning steps>"]}}
"""


class CompletionPatchGenerator(PatchGeneratorInterface):
    """Patch generator backed by an injected LLM completion callable.

    Same boundary pattern as the other LLM adapters: no provider dependency,
    fail-closed — unparseable output, an empty diff, or changed files outside
    the suspect list all fall back to the null generator. Output is a
    candidate hypothesis (confidence stays "unknown"); the gate runner and
    patch-risk classifier remain the arbiters.
    """

    version = "queue-items.v1"

    def __init__(
        self,
        *,
        complete: Callable[[str], str],
        model_id: str,
    ) -> None:
        self._complete = complete
        self.model_id = model_id
        self._null = NullPatchGenerator()

    def generate(self, context: RepairContextRecord) -> CandidatePatch:
        prompt = _PATCH_PROMPT.format(
            run_id=context.run_id,
            language=context.language,
            suspects=", ".join(context.file_suspects[:5]) or "none",
            alert_count=len(context.sarif_alerts_in_scope),
        )
        raw = self._complete(prompt)
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return self._null.generate(context)
        if not isinstance(parsed, dict):
            return self._null.generate(context)
        diff_text = parsed.get("diff_text")
        if not isinstance(diff_text, str) or "diff --git" not in diff_text:
            return self._null.generate(context)
        allowed = set(context.file_suspects)
        raw_changed = parsed.get("changed_files")
        changed_candidates = raw_changed if isinstance(raw_changed, list) else []
        changed = [f for f in changed_candidates if isinstance(f, str) and f in allowed]
        if not changed:
            return self._null.generate(context)
        raw_reasoning = parsed.get("reasoning")
        reasoning_candidates = raw_reasoning if isinstance(raw_reasoning, list) else []
        reasoning = [r for r in reasoning_candidates if isinstance(r, str)][:10]
        return CandidatePatch(
            run_id=context.run_id,
            candidate_index=context.candidate_index,
            diff_text=diff_text,
            changed_files=changed,
            changed_symbol_ids=[f"symbol:{f}:1" for f in changed],
            generation_method="llm_completion",
            generator_model=self.model_id,
            reasoning_chain=reasoning or ["llm completion patch candidate"],
            confidence="unknown",
            provenance={"version": self.version},
        )
