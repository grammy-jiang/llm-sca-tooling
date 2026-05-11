"""Stage 6b: Dynamic verdict hook (dormant until Phase 16)."""

from __future__ import annotations

from llm_sca_tooling.impl_check.models import DynamicVerdictRecord


def run_dynamic_hook(clause_id: str) -> DynamicVerdictRecord:
    """Phase 14: always returns available=False (Phase 16 activates)."""
    return DynamicVerdictRecord(
        clause_id=clause_id,
        stage="6b",
        verdict="unknown",
        available=False,
        confidence="unknown",
    )
