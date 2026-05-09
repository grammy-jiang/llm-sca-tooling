"""Prompt registry factory."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.mcp_server.prompt_registry import PromptRegistry
from llm_sca_tooling.mcp_server.sampling import SamplingCapabilityRecord


def default_prompt_registry(sampling: SamplingCapabilityRecord) -> PromptRegistry:
    return PromptRegistry(Path(__file__).parent / "prompts", sampling)
