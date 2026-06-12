"""Provider-backed completion callable for the LLM boundary adapters.

All four boundaries (hindsight relabeller, contract generator, QA synthesis,
trace summarizer) and the grounding adapter take an injected
``complete: (prompt) -> response`` callable. This module is the single place
that builds a live one, backed by the official Anthropic SDK.

Constraints honoured here:
- HC5: the SDK is an optional extra (``pip install llm-sca-tooling[llm]``);
  without it — or without ``ANTHROPIC_API_KEY`` in the environment — the
  factory reports unavailable and callers stay on their null adapters.
- HC1/HC6: the API key is read from the environment at call-construction time
  and never logged, stored, or echoed.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Callable
from typing import Any

__all__ = [
    "DEFAULT_MODEL_ID",
    "CompletionUnavailable",
    "completion_available",
    "get_completion_callable",
]

# Per Anthropic guidance the default is the latest Opus-tier model; override
# with LLM_SCA_MODEL for cost-sensitive batch runs.
DEFAULT_MODEL_ID = "claude-opus-4-8"
_MODEL_ENV = "LLM_SCA_MODEL"
_KEY_ENV = "ANTHROPIC_API_KEY"
_DEFAULT_MAX_TOKENS = 2048


class CompletionUnavailable(RuntimeError):  # noqa: N818 — matches EmbeddingUnavailable
    """Raised when no live completion callable can be constructed."""


def _sdk_installed() -> bool:
    return importlib.util.find_spec("anthropic") is not None


def completion_available() -> bool:
    """Cheap check: SDK importable and an API key present in the env."""
    return _sdk_installed() and bool(os.environ.get(_KEY_ENV))


def resolve_model_id(model_id: str | None = None) -> str:
    return model_id or os.environ.get(_MODEL_ENV) or DEFAULT_MODEL_ID


def get_completion_callable(
    model_id: str | None = None,
    *,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    client: Any | None = None,
) -> Callable[[str], str]:
    """Build a ``complete(prompt) -> text`` callable.

    Raises :class:`CompletionUnavailable` when the optional ``llm`` extra is
    not installed or no API key is configured. A pre-built ``client`` may be
    injected for tests.
    """
    resolved_model = resolve_model_id(model_id)
    if client is None:
        if not _sdk_installed():
            raise CompletionUnavailable(
                "anthropic SDK is not installed; "
                "install the 'llm' extra to enable live LLM boundaries"
            )
        if not os.environ.get(_KEY_ENV):
            raise CompletionUnavailable(
                f"{_KEY_ENV} is not set; export it to enable live LLM boundaries"
            )
        import anthropic  # noqa: PLC0415

        client = anthropic.Anthropic()

    def complete(prompt: str) -> str:
        response = client.messages.create(
            model=resolved_model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if getattr(response, "stop_reason", None) == "refusal":
            # Fail-closed: boundaries treat empty output as "no evidence".
            return ""
        return "".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        )

    return complete
