"""Tests for scope_audit."""

from __future__ import annotations

from llm_sca_tooling.patch_review.models import ProcessVerdict
from llm_sca_tooling.patch_review.scope_audit import audit_scope


def _events(*names: str) -> list[dict[str, object]]:
    return [{"type": n, "event_id": f"ev:{n}"} for n in names]


def test_compliant_run() -> None:
    result = audit_scope(
        run_id="r1",
        changed_paths=["src/x.py"],
        allowlisted_paths=["src/"],
        run_events=_events(
            "session_start", "harness_condition_recorded", "session_end"
        ),
    )
    assert result.process_verdict == ProcessVerdict.PROCESS_COMPLIANT
    assert result.trace_complete is True
    assert result.out_of_scope_writes == []


def test_out_of_scope_path_marks_noncompliant() -> None:
    result = audit_scope(
        run_id="r1",
        changed_paths=["etc/passwd"],
        allowlisted_paths=["src/"],
        run_events=_events(
            "session_start", "harness_condition_recorded", "session_end"
        ),
    )
    assert "etc/passwd" in result.out_of_scope_writes
    assert result.process_verdict == ProcessVerdict.PROCESS_NONCOMPLIANT


def test_run_id_none_marks_trace_incomplete() -> None:
    result = audit_scope(run_id=None, changed_paths=["src/x.py"])
    assert result.process_verdict == ProcessVerdict.TRACE_INCOMPLETE


def test_budget_hard_stop_marks_budget_exhausted() -> None:
    result = audit_scope(
        run_id="r1",
        changed_paths=[],
        run_events=_events(
            "session_start", "harness_condition_recorded", "session_end"
        ),
        budget_hard_stop=True,
    )
    assert result.process_verdict == ProcessVerdict.BUDGET_EXHAUSTED


def test_missing_required_event_marks_incomplete() -> None:
    result = audit_scope(
        run_id="r1",
        changed_paths=[],
        run_events=_events("session_start"),
    )
    assert "session_end" in result.missing_required_events
    assert result.process_verdict == ProcessVerdict.TRACE_INCOMPLETE


def test_denials_and_destructive_marks_noncompliant() -> None:
    result = audit_scope(
        run_id="r1",
        changed_paths=[],
        run_events=[
            {"type": "session_start", "event_id": "e1"},
            {"type": "harness_condition_recorded", "event_id": "e2"},
            {"type": "session_end", "event_id": "e3"},
            {"type": "approval_denied", "event_id": "e4"},
            {
                "type": "tool_call_completed",
                "permission_mode": "edit",
                "tool_name": "rm",
            },
            {"type": "budget_warning", "event_id": "b"},
            {"type": "context_compaction", "event_id": "c"},
        ],
        permission_mode="edit",
        destructive_tool_calls=[{"tool_name": "rm"}],
    )
    assert result.process_verdict == ProcessVerdict.PROCESS_NONCOMPLIANT
    assert result.tool_calls_vs_mode
    assert result.denial_events_present
    assert result.budget_events_present
    assert result.compaction_events_present


def test_explicit_trace_complete_override() -> None:
    result = audit_scope(
        run_id="r1",
        changed_paths=[],
        run_events=_events("session_start"),
        trace_complete=True,
    )
    assert result.trace_complete is True
    assert result.process_verdict == ProcessVerdict.PROCESS_COMPLIANT
