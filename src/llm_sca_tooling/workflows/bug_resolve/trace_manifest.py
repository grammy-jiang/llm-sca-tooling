"""Session trace manifest writer."""

from __future__ import annotations

from llm_sca_tooling.evaluation.models import now_ts
from llm_sca_tooling.workflows.bug_resolve.models import (
    SessionTraceManifest,
    WorkflowState,
)


def write_trace_manifest(
    *,
    state: WorkflowState,
    issue_text_hash: str,
    harness_condition_id: str,
    start_ts: str,
) -> SessionTraceManifest:
    gate_events = [
        f"gate:{g.get('candidate_index')}:{g.get('overall_gate_pass')}"
        for g in state.gate_results
    ]
    monitor_events_labels = [
        m.get("monitor_type", "unknown") for m in state.monitor_events
    ]
    return SessionTraceManifest(
        run_id=state.run_id,
        issue_text_hash=issue_text_hash,
        start_ts=start_ts,
        end_ts=now_ts(),
        stage_sequence=state.stage_history + [state.stage],
        artefact_refs=[
            f"artefact://investigate/{state.run_id}",
            f"artefact://patches/{state.run_id}",
            f"artefact://gates/{state.run_id}",
        ],
        gate_events=gate_events,
        monitor_events=monitor_events_labels,
        harness_condition_id=harness_condition_id,
    )
