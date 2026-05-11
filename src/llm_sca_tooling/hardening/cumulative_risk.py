"""Cumulative risk monitor.

Detects sequences of individually-allowed operations that, in aggregate,
exceed policy thresholds.  Fires a ``CumulativeRiskEvent`` when a pattern
threshold is crossed.
"""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from llm_sca_tooling.telemetry.logging import get_logger

__all__ = ["CumulativeRiskEvent", "CumulativeRiskMonitor"]

logger = get_logger(__name__)

PatternType = Literal[
    "repeated_identical_tool_calls",
    "repeated_failing_gate_no_change",
    "context_growth_no_evidence",
    "denied_operation_storm",
    "budget_exhaustion_pattern",
    "suspicious_multistep",
]


@dataclass
class CumulativeRiskEvent:
    event_id: str
    run_id: str
    pattern_type: PatternType
    contributing_events: list[str]
    risk_score: float
    threshold_exceeded: bool
    action_taken: str
    ts: str


@dataclass
class _ToolCallRecord:
    tool_name: str
    args_hash: str
    ts: str
    succeeded: bool
    denied: bool = False


@dataclass
class _GateRecord:
    gate_id: str
    passed: bool
    evidence_changed: bool
    ts: str


class CumulativeRiskMonitor:
    """Monitor a session for cumulative-risk patterns.

    Args:
        thresholds: Per-pattern threshold overrides.
        on_event: Optional callback for each ``CumulativeRiskEvent``.
    """

    _DEFAULT_THRESHOLDS: dict[str, int] = {
        "repeated_identical_tool_calls": 5,
        "repeated_failing_gate_no_change": 3,
        "denied_operation_storm": 5,
        "budget_exhaustion_pattern": 2,
    }

    def __init__(
        self,
        run_id: str,
        thresholds: dict[str, int] | None = None,
        on_event: Any | None = None,
    ) -> None:
        self._run_id = run_id
        self._thresholds = {**self._DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._on_event = on_event
        self._tool_calls: list[_ToolCallRecord] = []
        self._gate_records: list[_GateRecord] = []
        self._budget_hard_stops: int = 0
        self._events: list[CumulativeRiskEvent] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        succeeded: bool = True,
        denied: bool = False,
    ) -> None:
        import hashlib  # noqa: PLC0415
        import json  # noqa: PLC0415

        args_hash = hashlib.md5(  # noqa: S324  # nosec B324
            json.dumps(args, sort_keys=True).encode(),
            usedforsecurity=False,
        ).hexdigest()
        self._tool_calls.append(
            _ToolCallRecord(
                tool_name=tool_name,
                args_hash=args_hash,
                ts=datetime.now(UTC).isoformat(),
                succeeded=succeeded,
                denied=denied,
            )
        )
        self._check_all()

    def record_gate_result(
        self, gate_id: str, passed: bool, evidence_changed: bool
    ) -> None:
        self._gate_records.append(
            _GateRecord(
                gate_id=gate_id,
                passed=passed,
                evidence_changed=evidence_changed,
                ts=datetime.now(UTC).isoformat(),
            )
        )
        self._check_all()

    def record_budget_hard_stop(self) -> None:
        self._budget_hard_stops += 1
        self._check_all()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def events(self) -> list[CumulativeRiskEvent]:
        return list(self._events)

    # ------------------------------------------------------------------
    # Internal checks
    # ------------------------------------------------------------------

    def _check_all(self) -> None:
        self._check_repeated_tool_calls()
        self._check_repeated_failing_gate()
        self._check_denied_storm()
        self._check_budget_exhaustion()

    def _check_repeated_tool_calls(self) -> None:
        threshold = self._thresholds["repeated_identical_tool_calls"]
        counts: Counter[str] = Counter(
            f"{r.tool_name}:{r.args_hash}" for r in self._tool_calls
        )
        for key, count in counts.items():
            if count >= threshold:
                self._emit(
                    pattern_type="repeated_identical_tool_calls",
                    contributing=[f"{key} x{count}"],
                    risk_score=min(1.0, count / (threshold * 2)),
                    action="warn",
                )
                return

    def _check_repeated_failing_gate(self) -> None:
        threshold = self._thresholds["repeated_failing_gate_no_change"]
        consecutive = 0
        gate_id = None
        for gr in reversed(self._gate_records):
            if not gr.passed and not gr.evidence_changed:
                if gate_id is None:
                    gate_id = gr.gate_id
                if gr.gate_id == gate_id:
                    consecutive += 1
            else:
                break
        if consecutive >= threshold:
            self._emit(
                pattern_type="repeated_failing_gate_no_change",
                contributing=[f"{gate_id} x{consecutive}"],
                risk_score=min(1.0, consecutive / (threshold * 2)),
                action="warn",
            )

    def _check_denied_storm(self) -> None:
        threshold = self._thresholds["denied_operation_storm"]
        denied_count = sum(1 for r in self._tool_calls if r.denied)
        if denied_count >= threshold:
            self._emit(
                pattern_type="denied_operation_storm",
                contributing=[f"denied_ops={denied_count}"],
                risk_score=min(1.0, denied_count / (threshold * 2)),
                action="warn",
            )

    def _check_budget_exhaustion(self) -> None:
        threshold = self._thresholds["budget_exhaustion_pattern"]
        if self._budget_hard_stops >= threshold:
            self._emit(
                pattern_type="budget_exhaustion_pattern",
                contributing=[f"hard_stops={self._budget_hard_stops}"],
                risk_score=min(1.0, self._budget_hard_stops / (threshold * 2)),
                action="pause",
            )

    def _emit(
        self,
        pattern_type: PatternType,
        contributing: list[str],
        risk_score: float,
        action: str,
    ) -> None:
        # Avoid duplicate events for the same pattern in the same session
        existing = {e.pattern_type for e in self._events if e.threshold_exceeded}
        if pattern_type in existing:
            return
        event = CumulativeRiskEvent(
            event_id=f"crisk:{uuid.uuid4().hex[:10]}",
            run_id=self._run_id,
            pattern_type=pattern_type,
            contributing_events=contributing,
            risk_score=risk_score,
            threshold_exceeded=True,
            action_taken=action,
            ts=datetime.now(UTC).isoformat(),
        )
        self._events.append(event)
        logger.warning(
            "cumulative_risk: pattern=%s score=%.2f action=%s",
            pattern_type,
            risk_score,
            action,
        )
        if self._on_event is not None:
            self._on_event(event)
