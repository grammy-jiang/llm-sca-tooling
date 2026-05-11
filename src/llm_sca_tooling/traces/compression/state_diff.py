"""State diff and divergence point computation from two traces."""

from __future__ import annotations

from llm_sca_tooling.traces.artefact_store import load_events
from llm_sca_tooling.traces.models import (
    DivergencePoint,
    RawTraceArtefact,
    StateDiff,
)


def compute_state_diffs(
    pre_fix: RawTraceArtefact,
    post_fix: RawTraceArtefact,
) -> list[StateDiff]:
    """Compare two trace artefacts and return state diffs."""
    pre_events = load_events(pre_fix)
    post_events = load_events(post_fix)
    diffs: list[StateDiff] = []
    pre_funcs = {e.get("function", ""): e for e in pre_events}
    post_funcs = {e.get("function", ""): e for e in post_events}
    for func in set(pre_funcs) | set(post_funcs):
        pre = pre_funcs.get(func)
        post = post_funcs.get(func)
        if pre is None:
            diffs.append(
                StateDiff(
                    trace_run_id=post_fix.trace_run_id,
                    function_path=func,
                    diff_type="new_call",
                    confidence="heuristic",
                )
            )
        elif post is None:
            diffs.append(
                StateDiff(
                    trace_run_id=post_fix.trace_run_id,
                    function_path=func,
                    diff_type="missing_call",
                    confidence="heuristic",
                )
            )
        elif pre.get("event_type") != post.get("event_type"):
            pre_type = pre.get("event_type", "")
            post_type = post.get("event_type", "")
            diff_type = (
                "exception_vs_return"
                if {"exception", "return"} == {pre_type, post_type}
                else "path_divergence"
            )
            diffs.append(
                StateDiff(
                    trace_run_id=post_fix.trace_run_id,
                    function_path=func,
                    parameter_before=pre_type,
                    parameter_after=post_type,
                    diff_type=diff_type,
                    confidence="heuristic",
                )
            )
    return diffs


def compute_divergence_points(
    pre_fix: RawTraceArtefact,
    post_fix: RawTraceArtefact,
    diffs: list[StateDiff],
) -> list[DivergencePoint]:
    pre_events = load_events(pre_fix)
    post_events = load_events(post_fix)
    pre_by_func = {e.get("function", ""): e for e in pre_events}
    post_by_func = {e.get("function", ""): e for e in post_events}
    points: list[DivergencePoint] = []
    for diff in diffs:
        pre = pre_by_func.get(diff.function_path, {})
        post = post_by_func.get(diff.function_path, {})
        dtype = (
            "exception_raised_vs_not"
            if diff.diff_type == "exception_vs_return"
            else (
                "missing_call"
                if diff.diff_type == "missing_call"
                else (
                    "new_call"
                    if diff.diff_type == "new_call"
                    else "branch_taken_vs_not_taken"
                )
            )
        )
        points.append(
            DivergencePoint(
                trace_run_id=post_fix.trace_run_id,
                function_path=diff.function_path,
                file_path=str(pre.get("file_path", post.get("file_path", "unknown"))),
                line_number=int(pre.get("line_number", 0)),
                divergence_type=dtype,
                pre_fix_event_ref=pre.get("event_id"),
                post_fix_event_ref=post.get("event_id"),
                confidence="heuristic",
            )
        )
    return points
