"""Scope and permission audit derived from the patch-producing run record."""

from __future__ import annotations

from typing import Any

from llm_sca_tooling.patch_review.models import ProcessVerdict, ScopeAuditResult

REQUIRED_EVENT_TYPES: tuple[str, ...] = (
    "session_start",
    "harness_condition_recorded",
    "session_end",
)


def audit_scope(
    *,
    run_id: str | None,
    changed_paths: list[str],
    allowlisted_paths: list[str] | None = None,
    run_events: list[dict[str, Any]] | None = None,
    permission_mode: str | None = None,
    network_policy_violations: list[dict[str, Any]] | None = None,
    destructive_tool_calls: list[dict[str, Any]] | None = None,
    budget_hard_stop: bool = False,
    trace_complete: bool | None = None,
) -> ScopeAuditResult:
    """Compute scope/permission audit from a run record's events.

    Out-of-scope writes are computed by checking each ``changed_paths`` entry
    against ``allowlisted_paths`` (entries are treated as path prefixes). When
    ``allowlisted_paths`` is None all paths are considered in-scope.
    """
    events = run_events or []
    types_seen = [str(ev.get("type", "")) for ev in events]
    approval_events = [
        ev for ev in events if ev.get("type", "").startswith("approval_")
    ]
    denial_events = [ev for ev in events if str(ev.get("type", "")).endswith("_denied")]
    budget_events = [ev for ev in events if "budget" in str(ev.get("type", ""))]
    compaction_events = [ev for ev in events if "compact" in str(ev.get("type", ""))]
    missing = [t for t in REQUIRED_EVENT_TYPES if t not in types_seen]
    derived_trace = trace_complete if trace_complete is not None else not missing
    out_of_scope: list[str] = []
    if allowlisted_paths is not None:
        for path in changed_paths:
            if not any(
                path == allow or path.startswith(allow.rstrip("/") + "/")
                for allow in allowlisted_paths
            ):
                out_of_scope.append(path)

    tool_calls_vs_mode: list[dict[str, Any]] = []
    for ev in events:
        if str(ev.get("type", "")) == "tool_call_completed":
            mode = ev.get("permission_mode") or ""
            tool_calls_vs_mode.append(
                {
                    "tool": ev.get("tool_name"),
                    "mode_required": mode,
                    "mode_active": permission_mode,
                    "mode_match": (permission_mode is None)
                    or (mode == permission_mode),
                }
            )

    process_verdict = _derive_process_verdict(
        trace_complete=derived_trace,
        budget_hard_stop=budget_hard_stop,
        out_of_scope=out_of_scope,
        denial_events=denial_events,
        destructive_tool_calls=destructive_tool_calls or [],
        run_id=run_id,
    )

    return ScopeAuditResult(
        run_id=run_id,
        changed_paths=changed_paths,
        allowlisted_paths=allowlisted_paths or [],
        out_of_scope_writes=out_of_scope,
        tool_calls_vs_mode=tool_calls_vs_mode,
        network_use_vs_policy=network_policy_violations or [],
        required_events_present=[t for t in REQUIRED_EVENT_TYPES if t in types_seen],
        approval_events_present=[str(ev.get("event_id", "")) for ev in approval_events],
        denial_events_present=[str(ev.get("event_id", "")) for ev in denial_events],
        budget_events_present=[str(ev.get("event_id", "")) for ev in budget_events],
        compaction_events_present=[
            str(ev.get("event_id", "")) for ev in compaction_events
        ],
        missing_required_events=missing,
        trace_complete=derived_trace,
        process_verdict=process_verdict,
    )


def _derive_process_verdict(
    *,
    trace_complete: bool,
    budget_hard_stop: bool,
    out_of_scope: list[str],
    denial_events: list[dict[str, Any]],
    destructive_tool_calls: list[dict[str, Any]],
    run_id: str | None,
) -> ProcessVerdict:
    if run_id is None:
        return ProcessVerdict.TRACE_INCOMPLETE
    if not trace_complete:
        return ProcessVerdict.TRACE_INCOMPLETE
    if budget_hard_stop:
        return ProcessVerdict.BUDGET_EXHAUSTED
    if out_of_scope or destructive_tool_calls or denial_events:
        return ProcessVerdict.PROCESS_NONCOMPLIANT
    return ProcessVerdict.PROCESS_COMPLIANT
