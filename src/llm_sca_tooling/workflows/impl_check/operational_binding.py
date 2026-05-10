"""OperationalEvidenceBinding factory."""

from __future__ import annotations

from llm_sca_tooling.schemas.base import JsonObject
from llm_sca_tooling.workflows.impl_check.models import OperationalEvidenceBinding


def build_operational_binding(
    run_id: str,
    clause_id: str,
    *,
    graph_snapshot_id: str | None = None,
    resource_refs: list[str] | None = None,
    tool_calls: list[JsonObject] | None = None,
    gate_results: list[JsonObject] | None = None,
    stale_snapshot_flag: bool = False,
    mixed_snapshot_flag: bool = False,
    required_gate_events_present: bool = True,
    harness_condition_id: str = "",
) -> OperationalEvidenceBinding:
    return OperationalEvidenceBinding(
        run_id=run_id,
        clause_id=clause_id,
        graph_snapshot_id=graph_snapshot_id,
        resource_refs=resource_refs or [],
        tool_calls=tool_calls or [],
        gate_results=gate_results or [],
        stale_snapshot_flag=stale_snapshot_flag,
        mixed_snapshot_flag=mixed_snapshot_flag,
        required_gate_events_present=required_gate_events_present,
        harness_condition_id=harness_condition_id,
    )
