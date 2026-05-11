"""Operational evidence binding."""

from __future__ import annotations

from llm_sca_tooling.impl_check.models import OperationalEvidenceBinding


def bind_operational_evidence(
    *,
    run_id: str,
    clause_id: str,
    harness_condition_id: str,
    graph_snapshot_id: str | None = None,
    required_gate_events_present: bool = True,
) -> OperationalEvidenceBinding:
    return OperationalEvidenceBinding(
        run_id=run_id,
        clause_id=clause_id,
        graph_snapshot_id=graph_snapshot_id,
        resource_refs=[f"graph://snapshot/{graph_snapshot_id or 'unknown'}"],
        tool_calls=["run_implementation_check"],
        stale_snapshot_flag=graph_snapshot_id is None,
        required_gate_events_present=required_gate_events_present,
        harness_condition_id=harness_condition_id,
    )
