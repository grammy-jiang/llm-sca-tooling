"""Synchronous MCP-sampling client bridge.

Provides :class:`McpSamplingClient`, a synchronous wrapper that submits
``session.create_message()`` coroutines to the running event loop from a
worker thread, enabling synchronous tool handlers to invoke LLM sampling
without blocking the main async event loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class McpSamplingClient:
    """Synchronous wrapper for MCP ``session.create_message()`` sampling.

    Call :meth:`create_message` from any thread; it submits the coroutine to
    ``loop`` via :func:`asyncio.run_coroutine_threadsafe` and blocks until
    the LLM response arrives.

    The ``available`` attribute allows patch generators to detect whether a
    real sampling backend is present before attempting a call.
    """

    available: bool = True

    def __init__(
        self,
        session: Any,
        loop: asyncio.AbstractEventLoop,
        *,
        timeout: float = 60.0,
    ) -> None:
        self._session = session
        self._loop = loop
        self._timeout = timeout

    def create_message(self, prompt: str, max_tokens: int = 1024) -> dict[str, Any]:
        """Call the MCP client's LLM sampling and return ``{"content": str}``."""
        try:
            import mcp.types as mcp_types  # lazy import; only available at runtime

            messages: list[Any] = [
                mcp_types.SamplingMessage(
                    role="user",
                    content=mcp_types.TextContent(type="text", text=prompt),
                )
            ]
        except Exception:
            logger.debug("mcp.types unavailable; falling back to dict messages")
            messages = [{"role": "user", "content": {"type": "text", "text": prompt}}]

        try:
            coro = self._session.create_message(
                messages=messages, max_tokens=max_tokens
            )
            result = asyncio.run_coroutine_threadsafe(coro, self._loop).result(
                timeout=self._timeout
            )
            content = _extract_content(result)
            return {"content": content}
        except Exception:
            logger.debug("McpSamplingClient.create_message failed", exc_info=True)
            return {"content": ""}


def _extract_content(result: Any) -> str:
    """Extract text content from an MCP CreateMessageResult."""
    if result is None:
        return ""
    content = getattr(result, "content", None)
    if content is None:
        return ""
    if hasattr(content, "text"):
        return str(content.text)
    return str(content)


__all__ = ["McpSamplingClient"]
