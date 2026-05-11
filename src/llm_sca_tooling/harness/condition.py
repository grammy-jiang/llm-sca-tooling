"""Harness Condition Sheet writer.

Captures the runtime state at the time of a run and returns a structured
dict that matches the Phase H0 Harness Condition Sheet template.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import Any

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["HarnessConditionWriter"]

logger = get_logger(__name__)

_REQUIRED_FIELDS = (
    "run_id",
    "phase",
    "runtime_version",
    "model_backend",
    "toolset_hash",
    "permission_profile",
    "trace_completeness",
    "redaction_policy",
)


class HarnessConditionWriter:
    """Capture and optionally persist a Harness Condition Sheet.

    Usage::

        writer = HarnessConditionWriter()
        hcs = writer.capture(
            run_id="run:abc123",
            phase="H0",
            runtime_version="claude-code/1.0",
            model_backend="claude-sonnet-4-6",
            toolset_hash="<hash>",
            permission_profile="scoped-execute",
            context_budget=200_000,
            gates_enabled=["make verify"],
            gates_disabled=[],
            trace_location=".agent/traces/s1.jsonl",
            trace_completeness="complete",
            redaction_policy="default",
        )
    """

    def capture(
        self,
        run_id: str,
        phase: str,
        runtime_version: str,
        model_backend: str,
        toolset_hash: str,
        permission_profile: str,
        context_budget: int | None,
        gates_enabled: list[str],
        gates_disabled: list[str],
        trace_location: str | None,
        trace_completeness: str,
        redaction_policy: str,
    ) -> dict[str, Any]:
        """Return a Harness Condition Sheet dict.

        The returned dict includes all required fields from the Phase H0
        template. A run claiming a positive verdict must have
        ``trace_completeness == "complete"``.
        """
        hcs: dict[str, Any] = {
            "run_id": run_id,
            "report_date": datetime.now(UTC).date().isoformat(),
            "phase": phase,
            "python_version": sys.version,
            "runtime_version": runtime_version,
            "model_backend": model_backend,
            "toolset_hash": toolset_hash,
            "permission_profile": permission_profile,
            "context_budget": context_budget,
            "gates_enabled": gates_enabled,
            "gates_disabled": gates_disabled,
            "trace_location": trace_location,
            "trace_completeness": trace_completeness,
            "redaction_policy": redaction_policy,
        }
        logger.debug("Harness Condition Sheet captured for run %r", run_id)
        return hcs
