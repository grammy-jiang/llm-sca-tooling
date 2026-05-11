"""Scope and permission audit."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import ScopeAuditResult

DEFAULT_ALLOWLIST = [
    "src/",
    "tests/",
    "schemas/",
    "docs/",
    ".agent/",
    "AGENTS.md",
    "CLAUDE.md",
    "pyproject.toml",
    "tox.ini",
    "Makefile",
    ".github/workflows/",
]
REQUIRED_EVENTS = {"tool_call", "gate_result", "budget_event", "final_verdict"}


def audit_scope(
    *,
    changed_paths: list[str],
    run_id: str | None = None,
    run_events: list[str] | None = None,
    allowlisted_paths: list[str] | None = None,
) -> ScopeAuditResult:
    allowlist = allowlisted_paths or DEFAULT_ALLOWLIST
    out_of_scope = [
        path
        for path in changed_paths
        if not any(path.startswith(item) for item in allowlist)
    ]
    event_set = set(run_events or REQUIRED_EVENTS)
    missing = sorted(REQUIRED_EVENTS - event_set)
    trace_complete = not missing
    if out_of_scope:
        verdict = "process-noncompliant"
    elif "budget_hard_stop" in event_set:
        verdict = "budget-exhausted"
    elif not trace_complete:
        verdict = "trace-incomplete"
    else:
        verdict = "process-compliant"
    return ScopeAuditResult(
        run_id=run_id,
        changed_paths=changed_paths,
        allowlisted_paths=allowlist,
        out_of_scope_writes=out_of_scope,
        required_events_present=trace_complete,
        denial_events_present=bool(out_of_scope),
        budget_events_present="budget_event" in event_set,
        missing_required_events=missing,
        trace_complete=trace_complete,
        process_verdict=verdict,
    )
