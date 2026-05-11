"""Patch generator interface and null adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from llm_sca_tooling.sast_repair.models import RepairContext, SASTPatch

if TYPE_CHECKING:
    from llm_sca_tooling.mcp_server.sampling import SamplingClient


class PatchGeneratorInterface(ABC):
    model_id: str
    version: str

    @abstractmethod
    def generate(self, context: RepairContext) -> SASTPatch:
        raise NotImplementedError


class NullPatchGenerator(PatchGeneratorInterface):
    model_id = "phase12-null"
    version = "1"

    def generate(self, context: RepairContext) -> SASTPatch:
        changed = [context.file_path] if context.file_path else []
        diff = (
            f"diff --git a/{context.file_path} b/{context.file_path}\n"
            f"--- a/{context.file_path}\n+++ b/{context.file_path}\n"
            "@@ -1 +1 @@\n-old\n+old\n"
            if context.file_path
            else ""
        )
        return SASTPatch(
            alert_id=context.alert_id,
            diff_text=diff,
            changed_files=changed,
            generator_model=self.model_id,
            generation_method="null_repair",
            confidence="unknown",
            certificate_text="Null adapter produced deterministic no-op repair.",
            reasoning_chain=["null-mode"],
            dryrun_prediction_ref=f"dryrun:{context.alert_id}",
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

    def generate(self, context: RepairContext) -> SASTPatch:
        """Synchronously dispatch to sampling (or fall back).

        The MCP Sampling protocol is async; callers in async contexts should
        prefer :meth:`generate_async` when available.
        """
        import asyncio  # noqa: PLC0415

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Cannot call async from sync inside running loop — use null.
                return self._null.generate(context)
            return loop.run_until_complete(self.generate_async(context))
        except Exception:  # noqa: BLE001
            return self._null.generate(context)

    async def generate_async(self, context: RepairContext) -> SASTPatch:
        """Async patch generation via MCP Sampling."""
        from llm_sca_tooling.mcp_server.sampling import SamplingRequest  # noqa: PLC0415

        if not self._sampling.is_supported:
            return self._null.generate(context)

        prompt = (
            f"Generate a minimal unified diff to repair the following SAST alert.\n\n"
            f"Alert ID: {context.alert_id}\n"
            f"File: {context.file_path}\n"
            f"Explanation: {context.alert_explanation}\n\n"
            "Respond with only the unified diff text, no explanation."
        )
        request = SamplingRequest(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You are a security-aware code repair assistant.",
            max_tokens=1024,
        )
        response = await self._sampling.create_message(request)
        if not response.via_sampling or not response.content.strip():
            return self._null.generate(context)

        changed = [context.file_path] if context.file_path else []
        return SASTPatch(
            alert_id=context.alert_id,
            diff_text=response.content,
            changed_files=changed,
            generator_model=self.model_id,
            generation_method="sampling_repair",
            confidence="medium",
            certificate_text=(
                "Patch generated via MCP Sampling;"
                " requires deterministic gate verification."
            ),
            reasoning_chain=["sampling-mode"],
            dryrun_prediction_ref=f"dryrun:{context.alert_id}",
            provenance={"version": self.version, "model": response.model or "unknown"},
        )
