"""MCP Sampling capability detection and client."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "SamplingCapability",
    "SamplingRequest",
    "SamplingResponse",
    "detect_sampling",
]

# Type alias for the sampling send function injected from the MCP session.
# Signature: (messages, model_preferences, system_prompt, max_tokens) -> str
SamplingFn = Callable[
    [list[dict[str, Any]], dict[str, Any] | None, str | None, int],
    Awaitable[str],
]


class SamplingCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["supported", "unsupported", "unknown"]
    details: dict[str, Any] = Field(default_factory=dict)


class SamplingRequest(BaseModel):
    """A structured request to send to the MCP Sampling endpoint."""

    model_config = ConfigDict(extra="forbid")

    messages: list[dict[str, Any]]
    system_prompt: str | None = None
    max_tokens: int = 2048
    model_preferences: dict[str, Any] = Field(default_factory=dict)


class SamplingResponse(BaseModel):
    """Normalised response from the MCP Sampling endpoint."""

    model_config = ConfigDict(extra="forbid")

    content: str
    stop_reason: str | None = None
    model: str | None = None
    via_sampling: bool = True


class SamplingClient:
    """Wraps the MCP Sampling protocol for server-side use.

    The MCP server asks the *client* to invoke an LLM on its behalf via
    ``sampling/createMessage``. This class holds an optional injected send
    function (provided by the transport layer) and provides a ``create_message``
    helper that falls back to a null response when sampling is not available.
    """

    def __init__(
        self,
        capability: SamplingCapability,
        send_fn: SamplingFn | None = None,
    ) -> None:
        self._capability = capability
        self._send_fn = send_fn

    @property
    def status(self) -> str:
        return self._capability.status

    @property
    def is_supported(self) -> bool:
        return self._capability.status == "supported" and self._send_fn is not None

    async def create_message(
        self,
        request: SamplingRequest,
    ) -> SamplingResponse:
        """Send a ``sampling/createMessage`` request to the MCP client.

        Returns a ``SamplingResponse`` with ``via_sampling=False`` if the
        capability is not available or no send function is injected.
        """
        if not self.is_supported or self._send_fn is None:
            return SamplingResponse(
                content="",
                stop_reason="not_supported",
                via_sampling=False,
            )
        try:
            text = await self._send_fn(
                request.messages,
                request.model_preferences or None,
                request.system_prompt,
                request.max_tokens,
            )
            return SamplingResponse(content=text)
        except Exception as exc:  # noqa: BLE001
            return SamplingResponse(
                content="",
                stop_reason=f"error:{type(exc).__name__}",
                via_sampling=False,
            )


def detect_sampling(client_capabilities: dict[str, Any] | None) -> SamplingCapability:
    if client_capabilities is None:
        return SamplingCapability(status="unknown")
    sampling = client_capabilities.get("sampling")
    if isinstance(sampling, dict):
        return SamplingCapability(status="supported", details=sampling)
    if sampling is False:
        return SamplingCapability(status="unsupported")
    return SamplingCapability(status="unknown", details={"raw": sampling})
