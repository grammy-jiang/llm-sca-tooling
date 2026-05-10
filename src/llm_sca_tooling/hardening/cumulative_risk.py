"""Cumulative-risk monitoring."""

from __future__ import annotations

import uuid

from llm_sca_tooling.hardening.models import (
    CumulativeRiskEvent,
    CumulativeRiskPattern,
)
from llm_sca_tooling.schemas.base import JsonObject


class CumulativeRiskMonitor:
    def detect(
        self, *, run_id: str, events: list[JsonObject]
    ) -> list[CumulativeRiskEvent]:
        findings: list[CumulativeRiskEvent] = []
        identical = _repeated_identical(events)
        if identical:
            findings.append(
                _event(
                    run_id,
                    CumulativeRiskPattern.REPEATED_IDENTICAL_TOOL_CALLS,
                    identical,
                    0.8,
                )
            )
        denied = [
            str(item.get("event_id"))
            for item in events
            if item.get("policy_action") == "denied"
        ]
        if len(denied) >= 3:
            findings.append(
                _event(
                    run_id, CumulativeRiskPattern.DENIED_OPERATION_STORM, denied, 0.9
                )
            )
        hard_stops = [
            str(item.get("event_id"))
            for item in events
            if item.get("type") == "budget_hard_stop"
        ]
        if len(hard_stops) >= 2:
            findings.append(
                _event(
                    run_id,
                    CumulativeRiskPattern.BUDGET_EXHAUSTION_PATTERN,
                    hard_stops,
                    0.75,
                )
            )
        return findings


def _repeated_identical(events: list[JsonObject]) -> list[str]:
    seen: dict[str, list[str]] = {}
    for event in events:
        if event.get("type") != "tool_call":
            continue
        key = f"{event.get('tool')}:{event.get('args')}"
        seen.setdefault(key, []).append(str(event.get("event_id")))
    for ids in seen.values():
        if len(ids) > 3:
            return ids
    return []


def _event(
    run_id: str,
    pattern: CumulativeRiskPattern,
    contributing: list[str],
    score: float,
) -> CumulativeRiskEvent:
    return CumulativeRiskEvent(
        event_id=f"risk:{uuid.uuid4().hex}",
        run_id=run_id,
        pattern_type=pattern,
        contributing_events=contributing,
        risk_score=score,
        threshold_exceeded=True,
        action_taken="logged",
    )
