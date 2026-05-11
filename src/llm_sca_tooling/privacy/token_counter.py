"""TokenBudget exceeded error and per-request token counter."""

from __future__ import annotations


class TokenBudgetExceededError(Exception):
    """Raised when accumulated tokens exceed the configured hard limit."""


class TokenCounter:
    """Per-request token counter with configurable hard limits."""

    DEFAULT_HARD_LIMIT = 100_000

    def __init__(self, hard_limit: int = DEFAULT_HARD_LIMIT) -> None:
        self._hard_limit = hard_limit
        self._count = 0

    def count(self, text: str) -> int:
        """Estimate token count (4 chars per token heuristic)."""
        return max(1, len(text) // 4)

    def add(self, text: str) -> int:
        """Add tokens and raise TokenBudgetExceededError if over limit."""
        tokens = self.count(text)
        self._count += tokens
        if self._count > self._hard_limit:
            raise TokenBudgetExceededError(
                f"Token budget exceeded: {self._count} > {self._hard_limit}"
            )
        return self._count

    @property
    def total(self) -> int:
        """Return accumulated token count."""
        return self._count

    def reset(self) -> None:
        """Reset accumulated token count to zero."""
        self._count = 0
