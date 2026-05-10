"""Two-trace state-diff and divergence computation."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.traces.models import (
    DivergencePoint,
    StateDiff,
    TraceConfidence,
    TraceDiffType,
    TraceDivergenceType,
    TraceEvent,
    TraceEventType,
)


def load_trace_events(path: str | Path) -> list[TraceEvent]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    events: list[TraceEvent] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(TraceEvent.model_validate_json(line))
    return events


def compare_trace_events(
    *,
    trace_run_id: str,
    pre_events: list[TraceEvent],
    post_events: list[TraceEvent],
) -> tuple[list[StateDiff], list[DivergencePoint]]:
    pre_calls = [
        event for event in pre_events if event.event_type is TraceEventType.CALL
    ]
    post_calls = [
        event for event in post_events if event.event_type is TraceEventType.CALL
    ]
    diffs: list[StateDiff] = []
    points: list[DivergencePoint] = []
    pre_paths = [event.function_path for event in pre_calls]
    post_paths = [event.function_path for event in post_calls]
    for function_path in sorted(set(pre_paths) - set(post_paths)):
        event = next(item for item in pre_calls if item.function_path == function_path)
        diffs.append(
            StateDiff(
                trace_run_id=trace_run_id,
                function_path=function_path,
                diff_type=TraceDiffType.MISSING_CALL,
                confidence=TraceConfidence.HEURISTIC,
            )
        )
        points.append(
            _point(
                trace_run_id,
                event,
                TraceDivergenceType.MISSING_CALL,
                pre_event=event.event_id,
                note="function called before but not after",
            )
        )
    for function_path in sorted(set(post_paths) - set(pre_paths)):
        event = next(item for item in post_calls if item.function_path == function_path)
        diffs.append(
            StateDiff(
                trace_run_id=trace_run_id,
                function_path=function_path,
                diff_type=TraceDiffType.NEW_CALL,
                confidence=TraceConfidence.HEURISTIC,
            )
        )
        points.append(
            _point(
                trace_run_id,
                event,
                TraceDivergenceType.NEW_CALL,
                post_event=event.event_id,
                note="function called after but not before",
            )
        )
    for before, after in zip(pre_calls, post_calls, strict=False):
        if before.function_path != after.function_path:
            diffs.append(
                StateDiff(
                    trace_run_id=trace_run_id,
                    function_path=before.function_path,
                    parameter_before=before.arg_type_hints,
                    parameter_after=after.arg_type_hints,
                    diff_type=TraceDiffType.PATH_DIVERGENCE,
                    confidence=TraceConfidence.HEURISTIC,
                )
            )
            points.append(
                _point(
                    trace_run_id,
                    before,
                    TraceDivergenceType.CALL_ORDER_CHANGE,
                    pre_event=before.event_id,
                    post_event=after.event_id,
                    note=f"call order changed to {after.function_path}",
                )
            )
            break
    _append_exception_return_diffs(trace_run_id, pre_events, post_events, diffs, points)
    return diffs, points


def _append_exception_return_diffs(
    trace_run_id: str,
    pre_events: list[TraceEvent],
    post_events: list[TraceEvent],
    diffs: list[StateDiff],
    points: list[DivergencePoint],
) -> None:
    pre_by_path = _events_by_path(pre_events)
    post_by_path = _events_by_path(post_events)
    for function_path in sorted(set(pre_by_path) & set(post_by_path)):
        pre_types = {event.event_type for event in pre_by_path[function_path]}
        post_types = {event.event_type for event in post_by_path[function_path]}
        if (
            TraceEventType.EXCEPTION in pre_types
            and TraceEventType.RETURN in post_types
        ) or (
            TraceEventType.RETURN in pre_types
            and TraceEventType.EXCEPTION in post_types
        ):
            before = pre_by_path[function_path][0]
            after = post_by_path[function_path][0]
            diffs.append(
                StateDiff(
                    trace_run_id=trace_run_id,
                    function_path=function_path,
                    diff_type=TraceDiffType.EXCEPTION_VS_RETURN,
                    confidence=TraceConfidence.HEURISTIC,
                )
            )
            points.append(
                _point(
                    trace_run_id,
                    before,
                    TraceDivergenceType.EXCEPTION_RAISED_VS_NOT,
                    pre_event=before.event_id,
                    post_event=after.event_id,
                    note="exception/return behaviour changed",
                )
            )


def _events_by_path(events: list[TraceEvent]) -> dict[str, list[TraceEvent]]:
    grouped: dict[str, list[TraceEvent]] = {}
    for event in events:
        grouped.setdefault(event.function_path, []).append(event)
    return grouped


def _point(
    trace_run_id: str,
    event: TraceEvent,
    divergence_type: TraceDivergenceType,
    *,
    pre_event: str | None = None,
    post_event: str | None = None,
    note: str,
) -> DivergencePoint:
    return DivergencePoint(
        trace_run_id=trace_run_id,
        function_path=event.function_path,
        file_path=event.file_path,
        line_number=event.line_number,
        divergence_type=divergence_type,
        pre_fix_event_ref=pre_event,
        post_fix_event_ref=post_event,
        confidence=TraceConfidence.HEURISTIC,
        notes=note,
    )
