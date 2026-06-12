"""Shared LLM completion-callable factory for the boundary adapters."""

from llm_sca_tooling.llm.completion import (
    CompletionUnavailable,
    completion_available,
    get_completion_callable,
)

__all__ = [
    "CompletionUnavailable",
    "completion_available",
    "get_completion_callable",
]
