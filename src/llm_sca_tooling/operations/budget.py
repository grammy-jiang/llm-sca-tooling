"""Budget monitor for token, tool-call, retry, and wall-clock limits."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from llm_sca_tooling.config import BudgetConfig
from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["BudgetStatus", "BudgetMonitor"]

logger = get_logger(__name__)

_SOFT_WARNING_PCT = 0.80


@dataclass
class BudgetStatus:
    tokens_used: int
    tokens_limit: int | None
    tool_calls_used: int
    tool_calls_limit: int | None
    wall_seconds_used: float
    wall_seconds_limit: int | None
    retries_used: int
    retries_limit: int | None
    status: str = field(default="ok")  # ok | soft_warning | hard_stop


class BudgetMonitor:
    """Tracks session resource consumption and emits soft-warning or hard-stop signals.

    Args:
        config: Budget limits from the project configuration.
    """

    def __init__(self, config: BudgetConfig) -> None:
        self._config = config
        self._tokens_used = 0
        self._tool_calls_used = 0
        self._retries_used = 0
        self._start_time = time.monotonic()

    # ------------------------------------------------------------------
    # Recording methods
    # ------------------------------------------------------------------

    def record_tokens(self, count: int) -> BudgetStatus:
        """Record *count* tokens consumed and return the current status."""
        self._tokens_used += count
        status = self._compute_status()
        if status.status != "ok":
            logger.warning(
                "Budget %s: tokens %d / %s",
                status.status,
                self._tokens_used,
                self._config.max_tokens,
            )
        return status

    def record_tool_call(self) -> BudgetStatus:
        """Record one tool call and return the current status."""
        self._tool_calls_used += 1
        return self._compute_status()

    def record_retry(self) -> BudgetStatus:
        """Record one retry and return the current status."""
        self._retries_used += 1
        return self._compute_status()

    def check_wall_clock(self) -> BudgetStatus:
        """Return the current status based on elapsed wall-clock time."""
        return self._compute_status()

    def reset(self) -> None:
        """Reset all counters and restart the wall-clock timer."""
        self._tokens_used = 0
        self._tool_calls_used = 0
        self._retries_used = 0
        self._start_time = time.monotonic()

    # ------------------------------------------------------------------
    # Contribution point: threshold logic
    # ------------------------------------------------------------------

    def _compute_status(self) -> BudgetStatus:
        """Compute the aggregate budget status from all tracked metrics.

        Returns ``hard_stop`` if any metric meets or exceeds its limit,
        ``soft_warning`` if any metric exceeds 80 % of its limit, else ``ok``.
        """
        wall = time.monotonic() - self._start_time
        bs = BudgetStatus(
            tokens_used=self._tokens_used,
            tokens_limit=self._config.max_tokens,
            tool_calls_used=self._tool_calls_used,
            tool_calls_limit=self._config.max_tool_calls,
            wall_seconds_used=wall,
            wall_seconds_limit=self._config.max_wall_seconds,
            retries_used=self._retries_used,
            retries_limit=self._config.max_retries,
        )

        pairs: list[tuple[float, float | None]] = [
            (self._tokens_used, self._config.max_tokens),
            (self._tool_calls_used, self._config.max_tool_calls),
            (self._retries_used, self._config.max_retries),
            (wall, self._config.max_wall_seconds),
        ]

        for used, limit in pairs:
            if limit is None:
                continue
            if used >= limit:
                bs.status = "hard_stop"
                return bs

        for used, limit in pairs:
            if limit is None:
                continue
            if used >= limit * _SOFT_WARNING_PCT:
                bs.status = "soft_warning"
                return bs

        return bs
