"""Budget monitor skeleton for token, tool-call, retry, and wall-clock limits."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetStatus:
    tokens_used: int
    tokens_limit: int | None
    tool_calls_used: int
    tool_calls_limit: int | None
    wall_seconds_used: float
    wall_seconds_limit: int | None
    retries_used: int
    retries_limit: int | None
    status: str


class BudgetMonitor:
    def __init__(
        self,
        *,
        tokens_limit: int | None = None,
        tool_calls_limit: int | None = None,
        wall_seconds_limit: int | None = None,
        retries_limit: int | None = None,
        warning_fraction: float = 0.8,
    ) -> None:
        self.tokens_limit = tokens_limit
        self.tool_calls_limit = tool_calls_limit
        self.wall_seconds_limit = wall_seconds_limit
        self.retries_limit = retries_limit
        self.warning_fraction = warning_fraction
        self.reset()

    def record_tokens(self, count: int) -> BudgetStatus:
        if count < 0:
            raise ValueError("token count must be non-negative")
        self.tokens_used += count
        return self._status()

    def record_tool_call(self) -> BudgetStatus:
        self.tool_calls_used += 1
        return self._status()

    def record_retry(self) -> BudgetStatus:
        self.retries_used += 1
        return self._status()

    def check_wall_clock(self) -> BudgetStatus:
        return self._status()

    def reset(self) -> None:
        self.tokens_used = 0
        self.tool_calls_used = 0
        self.retries_used = 0
        self.started_at = time.monotonic()

    def _status(self) -> BudgetStatus:
        wall_seconds = time.monotonic() - self.started_at
        status = "ok"
        metrics = [
            (self.tokens_used, self.tokens_limit),
            (self.tool_calls_used, self.tool_calls_limit),
            (wall_seconds, self.wall_seconds_limit),
            (self.retries_used, self.retries_limit),
        ]
        if any(limit is not None and used >= limit for used, limit in metrics):
            status = "hard_stop"
        elif any(
            limit is not None and used >= limit * self.warning_fraction
            for used, limit in metrics
        ):
            status = "soft_warning"
        return BudgetStatus(
            tokens_used=self.tokens_used,
            tokens_limit=self.tokens_limit,
            tool_calls_used=self.tool_calls_used,
            tool_calls_limit=self.tool_calls_limit,
            wall_seconds_used=wall_seconds,
            wall_seconds_limit=self.wall_seconds_limit,
            retries_used=self.retries_used,
            retries_limit=self.retries_limit,
            status=status,
        )
