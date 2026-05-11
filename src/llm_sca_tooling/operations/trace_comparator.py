"""Trace comparator — compare two run-record event traces.

Compares two runs by:
- Stage sequence
- Tool / event-type sequence
- Evidence delta (new tool_result / graph_query events in one run vs the other)
- Policy events (deny counts)
- Approximate token cost
- Verification results (gate_passed / gate_failed events)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["TraceComparison", "compare_run_traces"]


@dataclass
class SequenceDiff:
    only_in_a: list[str] = field(default_factory=list)
    only_in_b: list[str] = field(default_factory=list)
    common: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.only_in_a or self.only_in_b)


@dataclass
class TraceComparison:
    run_a: str
    run_b: str
    stage_sequence: SequenceDiff = field(default_factory=SequenceDiff)
    event_type_sequence: SequenceDiff = field(default_factory=SequenceDiff)
    evidence_delta: dict[str, Any] = field(default_factory=dict)
    policy_events: dict[str, Any] = field(default_factory=dict)
    cost_delta: dict[str, Any] = field(default_factory=dict)
    verification_results: dict[str, Any] = field(default_factory=dict)
    summary: str = ""


def compare_run_traces(
    run_a_id: str,
    run_b_id: str,
    events_a: list[dict[str, Any]],
    events_b: list[dict[str, Any]],
) -> TraceComparison:
    """Compare the event traces of two runs.

    Args:
        run_a_id:  Identifier for the first run.
        run_b_id:  Identifier for the second run.
        events_a:  Ordered list of event dicts for run A.
        events_b:  Ordered list of event dicts for run B.
    """
    result = TraceComparison(run_a=run_a_id, run_b=run_b_id)

    result.stage_sequence = _diff_sequences(
        _extract_stages(events_a), _extract_stages(events_b)
    )
    result.event_type_sequence = _diff_sequences(
        _extract_types(events_a), _extract_types(events_b)
    )
    result.evidence_delta = _compare_evidence(events_a, events_b)
    result.policy_events = _compare_policy(events_a, events_b)
    result.cost_delta = _compare_cost(events_a, events_b)
    result.verification_results = _compare_verification(events_a, events_b)
    result.summary = _build_summary(result)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_stages(events: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    last: str | None = None
    for evt in events:
        s = str(evt.get("stage") or "")
        if s and s != last:
            seen.append(s)
            last = s
    return seen


def _extract_types(events: list[dict[str, Any]]) -> list[str]:
    return [str(e.get("type") or "") for e in events if e.get("type")]


def _diff_sequences(a: list[str], b: list[str]) -> SequenceDiff:
    set_a = set(a)
    set_b = set(b)
    return SequenceDiff(
        only_in_a=sorted(set_a - set_b),
        only_in_b=sorted(set_b - set_a),
        common=sorted(set_a & set_b),
    )


_EVIDENCE_TYPES = {"tool_result", "graph_query", "sarif_result", "static_analysis"}


def _compare_evidence(
    events_a: list[dict[str, Any]], events_b: list[dict[str, Any]]
) -> dict[str, Any]:
    count_a = sum(1 for e in events_a if e.get("type") in _EVIDENCE_TYPES)
    count_b = sum(1 for e in events_b if e.get("type") in _EVIDENCE_TYPES)
    return {
        "run_a_evidence_events": count_a,
        "run_b_evidence_events": count_b,
        "delta": count_b - count_a,
    }


def _compare_policy(
    events_a: list[dict[str, Any]], events_b: list[dict[str, Any]]
) -> dict[str, Any]:
    def _policy_counts(events: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in events:
            pa = e.get("policy_action")
            if pa:
                counts[str(pa)] = counts.get(str(pa), 0) + 1
        return counts

    return {
        "run_a": _policy_counts(events_a),
        "run_b": _policy_counts(events_b),
    }


def _compare_cost(
    events_a: list[dict[str, Any]], events_b: list[dict[str, Any]]
) -> dict[str, Any]:
    def _sum_tokens(events: list[dict[str, Any]]) -> int:
        return sum(int(e.get("token_count") or 0) for e in events)

    def _sum_wall_ms(events: list[dict[str, Any]]) -> int:
        return sum(int(e.get("wall_ms") or 0) for e in events)

    tokens_a = _sum_tokens(events_a)
    tokens_b = _sum_tokens(events_b)
    wall_a = _sum_wall_ms(events_a)
    wall_b = _sum_wall_ms(events_b)
    return {
        "token_delta": tokens_b - tokens_a,
        "run_a_tokens": tokens_a,
        "run_b_tokens": tokens_b,
        "wall_ms_delta": wall_b - wall_a,
        "run_a_wall_ms": wall_a,
        "run_b_wall_ms": wall_b,
    }


def _compare_verification(
    events_a: list[dict[str, Any]], events_b: list[dict[str, Any]]
) -> dict[str, Any]:
    def _gate_summary(events: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in events:
            etype = str(e.get("type") or "")
            if etype in ("gate_passed", "gate_failed", "verification_event"):
                counts[etype] = counts.get(etype, 0) + 1
        return counts

    return {
        "run_a": _gate_summary(events_a),
        "run_b": _gate_summary(events_b),
    }


def _build_summary(c: TraceComparison) -> str:
    parts: list[str] = []
    if c.stage_sequence.changed:
        parts.append(
            f"stage diff: +{c.stage_sequence.only_in_b} -{c.stage_sequence.only_in_a}"
        )
    ev = c.evidence_delta.get("delta", 0)
    if ev:
        parts.append(f"evidence delta: {ev:+d} events")
    tok = c.cost_delta.get("token_delta", 0)
    if tok:
        parts.append(f"token delta: {tok:+d}")
    return "; ".join(parts) if parts else "no significant differences"
